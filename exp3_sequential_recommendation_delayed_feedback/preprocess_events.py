"""Input normalization, history-only action vocabulary, and split manifest."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, ExperimentConfig
from input_normalization import (
    _enforce_temporal_split_contract,
    _normalize_log,
    _read_csv,
    required_input_paths,
    resolve_input_path,
)
from utilities import (
    next_day_start_ms,
    parse_primary_tag,
    require_columns,
    save_frame,
    save_json,
    stable_group,
)


@dataclass
class PreparedData:
    history_events: pd.DataFrame
    evaluation_events: pd.DataFrame
    action_vocabulary: pd.DataFrame
    candidate_actions: list[str]
    full_design_vocabulary: pd.DataFrame
    full_design_actions: list[str]
    split_manifest: dict[str, object]


def _attach_tags(
    history: pd.DataFrame,
    evaluation: pd.DataFrame,
    video: pd.DataFrame,
    cfg: ExperimentConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    require_columns(video, [cfg.video_col, cfg.tag_col], cfg.video_basic_file)
    tags = video[[cfg.video_col, cfg.tag_col]].copy()
    tags[cfg.video_col] = tags[cfg.video_col].astype(str)
    tags["primary_tag"] = tags[cfg.tag_col].map(parse_primary_tag)
    tags = tags.drop_duplicates(cfg.video_col, keep="first")
    outputs: list[pd.DataFrame] = []
    for frame in (history, evaluation):
        out = frame.merge(tags[[cfg.video_col, "primary_tag"]], on=cfg.video_col, how="left")
        out["primary_tag"] = out["primary_tag"].fillna(cfg.unknown_action_bucket).astype(str)
        out.loc[out["primary_tag"].eq(""), "primary_tag"] = cfg.unknown_action_bucket
        outputs.append(out)
    return outputs[0], outputs[1]


def _freeze_action_vocabulary(
    history: pd.DataFrame,
    top_k: int,
    cfg: ExperimentConfig,
    *,
    require_top_k: bool = True,
) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    valid = history.loc[~history["primary_tag"].isin([cfg.unknown_action_bucket, ""])].copy()
    counts = (
        valid.groupby("primary_tag", sort=False)
        .size()
        .rename("history_event_count")
        .reset_index()
        .sort_values(["history_event_count", "primary_tag"], ascending=[False, True], kind="stable")
        .reset_index(drop=True)
    )
    if require_top_k and len(counts) < top_k:
        raise RuntimeError(f"History contains only {len(counts)} usable tags; {top_k} are required.")
    selected_count = min(top_k, len(counts))
    selected = counts.head(selected_count).copy()
    selected["action_rank_in_history"] = np.arange(1, selected_count + 1)
    selected["action_id"] = [f"action_{rank:02d}" for rank in range(1, selected_count + 1)]
    selected["action_display_name"] = "Tag " + selected["primary_tag"].astype(str)
    selected["is_candidate_action"] = True
    selected["is_residual_action"] = False
    residual = pd.DataFrame(
        [
            {
                "primary_tag": cfg.residual_action_bucket,
                "history_event_count": int(len(history) - history["primary_tag"].isin(selected["primary_tag"]).sum()),
                "action_rank_in_history": selected_count + 1,
                "action_id": cfg.residual_action_bucket,
                "action_display_name": "Residual action bucket",
                "is_candidate_action": False,
                "is_residual_action": True,
            }
        ]
    )
    vocabulary = pd.concat([selected, residual], ignore_index=True)
    lookup = dict(zip(selected["primary_tag"].astype(str), selected["action_id"].astype(str)))
    return vocabulary, lookup, selected["action_id"].astype(str).tolist()


def _action_space_coverage(
    frame: pd.DataFrame,
    selected_tags: set[str],
    split_id: str,
    design_scope: str,
) -> dict[str, object]:
    usable = ~frame["primary_tag"].isin([DEFAULT_CONFIG.unknown_action_bucket, ""])
    selected = frame["primary_tag"].isin(selected_tags)
    usable_count = int(usable.sum())
    selected_count = int(selected.sum())
    return {
        "split_id": split_id,
        "design_scope": design_scope,
        "selected_action_count": len(selected_tags),
        "all_event_count": int(len(frame)),
        "usable_tag_event_count": usable_count,
        "selected_event_count": selected_count,
        "selected_action_exposure_mass_coverage": selected_count / len(frame) if len(frame) else np.nan,
        "selected_action_usable_tag_coverage": selected_count / usable_count if usable_count else np.nan,
    }

def _apply_vocabulary(
    frame: pd.DataFrame,
    lookup: dict[str, str],
    candidate_actions: list[str],
    split_id: str,
    cfg: ExperimentConfig,
) -> pd.DataFrame:
    out = frame.copy()
    out["action_id"] = out["primary_tag"].map(lookup).fillna(cfg.residual_action_bucket)
    out["is_candidate_action"] = out["action_id"].isin(candidate_actions)
    out["split_id"] = split_id
    out["reference_fold_id"] = out[cfg.user_col].map(
        lambda value: stable_group(value, cfg.reference_fold_count, cfg.reference_fold_hash_salt)
    ).astype(np.int8)
    out["source_event_id"] = [f"{split_id}::{index:09d}" for index in range(len(out))]
    return out


def prepare_events(
    input_root: Path,
    output_dir: Path,
    run_tier: str,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> PreparedData:
    paths = required_input_paths(input_root, cfg)
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required Exp3 inputs: {[str(path) for path in missing]}")
    history = _normalize_log(_read_csv(paths[0]), cfg.history_log, cfg)
    evaluation = _normalize_log(_read_csv(paths[1]), cfg.evaluation_log, cfg)
    history, evaluation, temporal_audit = _enforce_temporal_split_contract(
        history, evaluation, cfg
    )
    video = _read_csv(paths[2])
    history, evaluation = _attach_tags(history, evaluation, video, cfg)
    primary_top_k = cfg.action_top_k(run_tier)
    vocabulary, lookup, candidate_actions = _freeze_action_vocabulary(
        history, primary_top_k, cfg, require_top_k=True
    )
    full_vocabulary, full_lookup, full_actions = _freeze_action_vocabulary(
        history, cfg.action_top_k_full, cfg, require_top_k=False
    )
    primary_tags = set(vocabulary.loc[vocabulary["is_candidate_action"], "primary_tag"].astype(str))
    full_tags = set(full_vocabulary.loc[full_vocabulary["is_candidate_action"], "primary_tag"].astype(str))
    coverage_rows = [
        _action_space_coverage(history, primary_tags, "history", "active_run"),
        _action_space_coverage(evaluation, primary_tags, "evaluation", "active_run"),
        _action_space_coverage(history, full_tags, "history", "full_design_preflight"),
        _action_space_coverage(evaluation, full_tags, "evaluation", "full_design_preflight"),
    ]
    history = _apply_vocabulary(history, lookup, candidate_actions, "history", cfg)
    evaluation = _apply_vocabulary(evaluation, lookup, candidate_actions, "evaluation", cfg)
    history["full_design_action_id"] = history["primary_tag"].map(full_lookup).fillna(cfg.residual_action_bucket)
    evaluation["full_design_action_id"] = evaluation["primary_tag"].map(full_lookup).fillna(cfg.residual_action_bucket)
    history["is_full_design_candidate_action"] = history["full_design_action_id"].isin(full_actions)
    evaluation["is_full_design_candidate_action"] = evaluation["full_design_action_id"].isin(full_actions)

    history_days = sorted(history["calendar_day"].unique().tolist())
    evaluation_days = sorted(evaluation["calendar_day"].unique().tolist())
    if not history_days or not evaluation_days:
        raise RuntimeError("History or evaluation split has no calendar days.")

    split_preflight = {
        **temporal_audit,
        "history_calendar_day_min": str(history_days[0]),
        "history_calendar_day_max": str(history_days[-1]),
        "evaluation_calendar_day_min": str(evaluation_days[0]),
        "evaluation_calendar_day_max": str(evaluation_days[-1]),
        "history_time_min_ms": int(history[cfg.time_col].min()),
        "history_time_max_ms": int(history[cfg.time_col].max()),
        "evaluation_time_min_ms": int(evaluation[cfg.time_col].min()),
        "evaluation_time_max_ms": int(evaluation[cfg.time_col].max()),
        "history_time_max_utc": pd.to_datetime(
            int(history[cfg.time_col].max()), unit="ms", utc=True
        ).isoformat(),
        "evaluation_time_min_utc": pd.to_datetime(
            int(evaluation[cfg.time_col].min()), unit="ms", utc=True
        ).isoformat(),
    }
    save_json(split_preflight, output_dir / "diagnostics" / "exp3_split_preflight.json")
    boundary_ms = int(temporal_audit["split_boundary_time_ms"])
    manifest = {
        "timezone_name": cfg.timezone_name,
        "timezone_rule": cfg.timezone_rule,
        "interval_convention": "left_closed_right_open",
        "history_start_local_date": cfg.history_start_local_date,
        "history_start_boundary_time_ms": int(temporal_audit["history_start_time_ms"]),
        "history_events_excluded_before_start": temporal_audit[
            "history_events_excluded_before_start"
        ],
        "history_prestart_fraction": temporal_audit["history_prestart_fraction"],
        "max_prestart_history_fraction": cfg.max_prestart_history_fraction,
        "split_boundary_local_date": cfg.split_boundary_local_date,
        "split_boundary_time_ms": boundary_ms,
        "boundary_policy": temporal_audit["boundary_policy"],
        "raw_strict_event_time_nonoverlap": temporal_audit[
            "raw_strict_event_time_nonoverlap"
        ],
        "raw_overlap_width_ms": temporal_audit["raw_overlap_width_ms"],
        "evaluation_events_excluded_before_boundary": temporal_audit[
            "evaluation_events_excluded_before_boundary"
        ],
        "evaluation_preboundary_fraction": temporal_audit[
            "evaluation_preboundary_fraction"
        ],
        "max_preboundary_evaluation_fraction": cfg.max_preboundary_evaluation_fraction,
        "strict_event_time_nonoverlap": temporal_audit[
            "strict_event_time_nonoverlap"
        ],
        "history_calendar_days": history_days,
        "evaluation_calendar_days": evaluation_days,
        "history_day_count": len(history_days),
        "evaluation_day_count": len(evaluation_days),
        "history_start_time": int(history[cfg.time_col].min()),
        "history_end_time_exclusive": boundary_ms,
        "evaluation_start_time": int(evaluation[cfg.time_col].min()),
        "evaluation_end_time_exclusive": next_day_start_ms(
            evaluation_days[-1], cfg.timezone_name
        ),
        "first_source_event_time": int(min(history[cfg.time_col].min(), evaluation[cfg.time_col].min())),
        "last_source_event_time": int(max(history[cfg.time_col].max(), evaluation[cfg.time_col].max())),
        "history_event_count": int(len(history)),
        "evaluation_event_count": int(len(evaluation)),
        "candidate_action_count": len(candidate_actions),
        "residual_is_candidate": False,
    }
    save_json(manifest, output_dir / "design" / "exp3_split_manifest.json")
    save_frame(vocabulary, output_dir / "design" / "exp3_action_vocabulary.csv")
    save_frame(full_vocabulary, output_dir / "design" / "exp3_full_design_action_vocabulary.csv")
    save_frame(pd.DataFrame(coverage_rows), output_dir / "tables" / "exp3_action_space_coverage.csv")
    save_frame(history, output_dir / "processed" / "exp3_history_events.parquet")
    save_frame(evaluation, output_dir / "processed" / "exp3_evaluation_events.parquet")
    return PreparedData(
        history, evaluation, vocabulary, candidate_actions,
        full_vocabulary, full_actions, manifest
    )

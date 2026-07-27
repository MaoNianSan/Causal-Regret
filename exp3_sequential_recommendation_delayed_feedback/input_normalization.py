"""Low-memory input resolution, normalization, and frozen temporal split contract."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, ExperimentConfig
from utilities import calendar_day, coerce_binary, coerce_numeric, day_start_ms, require_columns


def resolve_input_path(input_root: Path, filename: str) -> Path:
    direct = input_root / filename
    return direct if direct.exists() else input_root / "data" / filename


def required_input_paths(input_root: Path, cfg: ExperimentConfig = DEFAULT_CONFIG) -> list[Path]:
    return [
        resolve_input_path(input_root, cfg.history_log),
        resolve_input_path(input_root, cfg.evaluation_log),
        resolve_input_path(input_root, cfg.video_basic_file),
    ]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, low_memory=False)


def _normalize_log(frame: pd.DataFrame, label: str, cfg: ExperimentConfig) -> pd.DataFrame:
    require_columns(
        frame,
        [cfg.user_col, cfg.video_col, cfg.time_col, cfg.duration_col],
        label,
    )
    out = frame.copy()
    for column in (
        cfg.click_col,
        cfg.long_view_col,
        cfg.like_col,
        cfg.follow_col,
        cfg.comment_col,
        cfg.forward_col,
    ):
        out[column] = coerce_binary(out[column]) if column in out else 0
    for column in (cfg.time_col, cfg.duration_col, cfg.play_time_col):
        out[column] = coerce_numeric(out[column]) if column in out else 0.0
    # Validate identifiers before string conversion. Casting first would turn
    # missing identifiers into the literal string "nan" and silently retain
    # them as real users/videos.
    user_valid = out[cfg.user_col].notna()
    video_valid = out[cfg.video_col].notna()
    out = out[
        user_valid
        & video_valid
        & out[cfg.time_col].gt(0)
        & out[cfg.duration_col].gt(0)
    ].copy()
    out[cfg.user_col] = out[cfg.user_col].astype(str).str.strip()
    out[cfg.video_col] = out[cfg.video_col].astype(str).str.strip()
    invalid_tokens = {"", "nan", "none", "null"}
    out = out[
        ~out[cfg.user_col].str.lower().isin(invalid_tokens)
        & ~out[cfg.video_col].str.lower().isin(invalid_tokens)
    ].copy()
    out[cfg.time_col] = out[cfg.time_col].astype(np.int64)
    out["calendar_day"] = calendar_day(
        out[cfg.time_col], cfg.timezone_name
    ).to_numpy()
    out["watch_ratio"] = (
        out[cfg.play_time_col].astype(float) / out[cfg.duration_col].astype(float).clip(lower=1.0)
    ).clip(0.0, 1.0)
    out["short_term_proxy"] = (
        0.4 * out[cfg.click_col].astype(float)
        + 0.4 * out[cfg.long_view_col].astype(float)
        + 0.2 * out["watch_ratio"].astype(float)
    )
    return out.sort_values([cfg.user_col, cfg.time_col], kind="stable").reset_index(drop=True)


def _enforce_temporal_split_contract(
    history: pd.DataFrame,
    evaluation: pd.DataFrame,
    cfg: ExperimentConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Apply the frozen local-midnight boundary and audit any quarantined rows."""
    if history.empty or evaluation.empty:
        raise RuntimeError("History or evaluation split has no valid normalized events.")
    history_start_ms = day_start_ms(
        cfg.history_start_local_date, cfg.timezone_name
    )
    boundary_ms = day_start_ms(
        cfg.split_boundary_local_date, cfg.timezone_name
    )
    history_times = history[cfg.time_col].to_numpy(np.int64)
    evaluation_times = evaluation[cfg.time_col].to_numpy(np.int64)
    history_prestart = history_times < history_start_ms
    history_crosses = history_times >= boundary_ms
    evaluation_preboundary = evaluation_times < boundary_ms
    excluded_history_count = int(history_prestart.sum())
    excluded_history_fraction = excluded_history_count / len(history)
    excluded_evaluation_count = int(evaluation_preboundary.sum())
    excluded_evaluation_fraction = (
        excluded_evaluation_count / len(evaluation) if len(evaluation) else 0.0
    )

    if excluded_history_fraction > cfg.max_prestart_history_fraction:
        raise RuntimeError(
            "INPUT_HISTORY_PRESTART_EXCESS: history contains "
            f"{excluded_history_count} pre-start events "
            f"({excluded_history_fraction:.6%}), above the frozen "
            f"{cfg.max_prestart_history_fraction:.6%} limit."
        )
    if bool(history_crosses.any()):
        raise RuntimeError(
            "INPUT_HISTORY_CROSSES_FROZEN_BOUNDARY: history contains "
            f"{int(history_crosses.sum())} events at or after "
            f"{cfg.split_boundary_local_date} 00:00 {cfg.timezone_name}."
        )
    if excluded_evaluation_fraction > cfg.max_preboundary_evaluation_fraction:
        raise RuntimeError(
            "INPUT_EVALUATION_PREBOUNDARY_EXCESS: evaluation contains "
            f"{excluded_evaluation_count} pre-boundary events "
            f"({excluded_evaluation_fraction:.6%}), above the frozen "
            f"{cfg.max_preboundary_evaluation_fraction:.6%} limit."
        )

    retained_history = history.loc[~history_prestart].copy()
    retained_evaluation = evaluation.loc[~evaluation_preboundary].copy()
    if retained_history.empty:
        raise RuntimeError("History split has no events at or after the frozen start.")
    if retained_evaluation.empty:
        raise RuntimeError("Evaluation split has no events at or after the frozen boundary.")

    raw_history_max = int(history_times.max())
    raw_evaluation_min = int(evaluation_times.min())
    retained_history_min = int(retained_history[cfg.time_col].min())
    retained_history_max = int(retained_history[cfg.time_col].max())
    retained_evaluation_min = int(retained_evaluation[cfg.time_col].min())
    audit = {
        "timezone_name": cfg.timezone_name,
        "timezone_rule": cfg.timezone_rule,
        "history_start_local_date": cfg.history_start_local_date,
        "history_start_time_ms": history_start_ms,
        "history_start_time_utc": pd.to_datetime(
            history_start_ms, unit="ms", utc=True
        ).isoformat(),
        "split_boundary_local_date": cfg.split_boundary_local_date,
        "split_boundary_time_ms": boundary_ms,
        "split_boundary_time_utc": pd.to_datetime(boundary_ms, unit="ms", utc=True).isoformat(),
        "boundary_policy": "quarantine_events_outside_frozen_split_boundaries",
        "raw_history_time_max_ms": raw_history_max,
        "raw_evaluation_time_min_ms": raw_evaluation_min,
        "raw_strict_event_time_nonoverlap": raw_history_max < raw_evaluation_min,
        "raw_overlap_width_ms": max(0, raw_history_max - raw_evaluation_min),
        "history_events_excluded_before_start": excluded_history_count,
        "history_prestart_fraction": excluded_history_fraction,
        "max_prestart_history_fraction": cfg.max_prestart_history_fraction,
        "history_events_excluded_at_or_after_boundary": int(history_crosses.sum()),
        "evaluation_events_excluded_before_boundary": excluded_evaluation_count,
        "evaluation_preboundary_fraction": excluded_evaluation_fraction,
        "max_preboundary_evaluation_fraction": cfg.max_preboundary_evaluation_fraction,
        "retained_history_event_count": int(len(retained_history)),
        "retained_evaluation_event_count": int(len(retained_evaluation)),
        "retained_history_time_min_ms": retained_history_min,
        "retained_history_time_max_ms": retained_history_max,
        "retained_evaluation_time_min_ms": retained_evaluation_min,
        "strict_event_time_nonoverlap": retained_history_max < retained_evaluation_min,
    }
    if not bool(audit["strict_event_time_nonoverlap"]):
        raise RuntimeError(
            "INPUT_SPLIT_OVERLAP_AFTER_BOUNDARY_POLICY: retained history and evaluation "
            "events are not strictly time ordered."
        )
    return (
        retained_history.reset_index(drop=True),
        retained_evaluation.reset_index(drop=True),
        audit,
    )


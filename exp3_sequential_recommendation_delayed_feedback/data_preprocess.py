"""KuaiRand preprocessing with a history-defined action vocabulary.

Only the standard recommendation logs are used in the primary Exp3 target.  The
random-exposure stream is a separate intervention regime in KuaiRand; because
this protocol has no matched historical random stream, it is not mixed into
main-period outcome construction.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, ExperimentConfig
from utils import EPS, coerce_binary, coerce_numeric, logical_path, maybe_save_parquet, parse_primary_tag, read_csv_checked, require_columns, save_dataframe, utf8_safe_text


@dataclass
class PreparedLogs:
    history_standard: pd.DataFrame
    main_standard: pd.DataFrame
    action_map: pd.DataFrame
    actions: list[str]
    candidate_action_indices: np.ndarray


def resolve_input_path(root: Path, filename: str) -> Path:
    direct = root / filename
    if direct.exists():
        return direct
    return root / "data" / filename


def required_input_paths(root: Path, cfg: ExperimentConfig = DEFAULT_CONFIG) -> list[Path]:
    return [
        resolve_input_path(root, cfg.main_log),
        resolve_input_path(root, cfg.history_log),
        resolve_input_path(root, cfg.video_basic_file),
    ]


def _load_log(root: Path, filename: str, cfg: ExperimentConfig, sample_users: int | None) -> pd.DataFrame:
    df = read_csv_checked(resolve_input_path(root, filename))
    require_columns(df, [cfg.user_col, cfg.video_col, cfg.time_col, cfg.duration_col], filename)
    if sample_users is not None and sample_users > 0:
        keep = sorted(df[cfg.user_col].dropna().astype(str).unique())[:sample_users]
        df[cfg.user_col] = df[cfg.user_col].astype(str)
        df = df[df[cfg.user_col].isin(keep)].copy()
    return df


def _normalize(df: pd.DataFrame, cfg: ExperimentConfig) -> pd.DataFrame:
    out = df.copy()
    for col in [cfg.click_col, cfg.long_view_col, cfg.like_col, cfg.follow_col, cfg.comment_col, cfg.forward_col]:
        out[col] = coerce_binary(out[col]) if col in out.columns else 0
    for col in [cfg.time_col, cfg.play_time_col, cfg.duration_col]:
        out[col] = coerce_numeric(out[col]) if col in out.columns else 0.0
    out[cfg.user_col] = out[cfg.user_col].astype(str)
    out[cfg.video_col] = out[cfg.video_col].astype(str)
    keep = (out[cfg.time_col] > 0) & (out[cfg.duration_col] > 0) & out[cfg.user_col].notna() & out[cfg.video_col].notna()
    return out.loc[keep].copy()


def _video_tag_map(root: Path, cfg: ExperimentConfig) -> pd.DataFrame:
    video = read_csv_checked(resolve_input_path(root, cfg.video_basic_file))
    require_columns(video, [cfg.video_col, cfg.action_source_col], cfg.video_basic_file)
    video = video[[cfg.video_col, cfg.action_source_col]].copy()
    video[cfg.video_col] = video[cfg.video_col].astype(str)
    video["primary_tag"] = video[cfg.action_source_col].map(parse_primary_tag)
    return video.drop_duplicates(cfg.video_col)


def _attach_features(df: pd.DataFrame, tag_map: pd.DataFrame, cfg: ExperimentConfig, origin: str) -> pd.DataFrame:
    out = df.merge(tag_map[[cfg.video_col, "primary_tag"]], on=cfg.video_col, how="left")
    out["primary_tag"] = out["primary_tag"].fillna(cfg.unknown_action_bucket).map(parse_primary_tag)
    out["primary_tag"] = out["primary_tag"].replace({"": cfg.unknown_action_bucket, "nan": cfg.unknown_action_bucket})
    out["stream_origin"] = origin
    out["watch_ratio"] = (out[cfg.play_time_col] / (out[cfg.duration_col] + EPS)).clip(0.0, 1.0)
    out["short_term_composite"] = (
        0.5 * out[cfg.long_view_col].astype(float)
        + 1.0 * out[cfg.like_col].astype(float)
        + 1.0 * out[cfg.comment_col].astype(float)
        + 1.0 * out[cfg.forward_col].astype(float)
        + 1.5 * out[cfg.follow_col].astype(float)
    )
    out["short_term_proxy"] = (
        0.4 * out[cfg.click_col].astype(float)
        + 0.4 * out[cfg.long_view_col].astype(float)
        + 0.2 * out["watch_ratio"].astype(float)
    )
    return out.sort_values([cfg.user_col, cfg.time_col], kind="stable").reset_index(drop=True)


def _make_action_map(history_standard: pd.DataFrame, cfg: ExperimentConfig) -> tuple[dict[str, str], pd.DataFrame, list[str], np.ndarray]:
    """Choose coherent category actions using history only.

    ``other`` and missing tags remain in event accounting, but are excluded from
    the candidate action set.  They are not meaningful recommendation actions.
    """
    valid = history_standard.loc[history_standard["primary_tag"].astype(str).ne(cfg.unknown_action_bucket)].copy()
    counts = valid["primary_tag"].astype(str).value_counts(dropna=False)
    top_tags = counts.head(cfg.action_top_k).index.astype(str).tolist()
    if len(top_tags) < cfg.main_top_k:
        raise ValueError("History split does not contain enough non-missing action tags for the requested top-k evaluation.")
    lookup = {tag: tag for tag in top_tags}
    actions = top_tags + [cfg.residual_action_bucket]
    table = history_standard["primary_tag"].astype(str).value_counts(dropna=False).rename_axis("primary_tag").reset_index(name="n_history_standard_events")
    table["action_bucket"] = table["primary_tag"].map(lambda x: lookup.get(x, cfg.residual_action_bucket))
    table["in_candidate_action_vocabulary"] = table["primary_tag"].isin(top_tags)
    candidate_idx = np.arange(len(top_tags), dtype=int)
    return lookup, table, actions, candidate_idx


def _apply_action_vocab(df: pd.DataFrame, lookup: dict[str, str], cfg: ExperimentConfig) -> pd.DataFrame:
    out = df.copy()
    out["action_bucket"] = out["primary_tag"].astype(str).map(lambda x: lookup.get(x, cfg.residual_action_bucket))
    return out


def write_precheck(root: Path, output_dir: Path, cfg: ExperimentConfig) -> None:
    rows = []
    for filename in [cfg.main_log, cfg.history_log, cfg.video_basic_file, cfg.random_log, cfg.user_feature_file, cfg.video_stat_file]:
        path = resolve_input_path(root, filename)
        row = {"file_name": filename, "path": logical_path(path, root), "required_for_primary": filename in {cfg.main_log, cfg.history_log, cfg.video_basic_file}, "exists": path.exists(), "n_columns": 0, "columns": ""}
        if path.exists():
            try:
                head = pd.read_csv(path, nrows=3)
                row["n_columns"] = len(head.columns)
                row["columns"] = ";".join(head.columns.astype(str))
            except Exception as exc:
                row["columns"] = utf8_safe_text(f"READ_ERROR: {exc}")
        rows.append(row)
    save_dataframe(pd.DataFrame(rows), output_dir / "checks" / "input_schema_report.csv")


def prepare_logs(root: Path, output_dir: Path, cfg: ExperimentConfig = DEFAULT_CONFIG, sample_users: int | None = None) -> PreparedLogs:
    write_precheck(root, output_dir, cfg)
    tag_map = _video_tag_map(root, cfg)
    history = _attach_features(_normalize(_load_log(root, cfg.history_log, cfg, sample_users), cfg), tag_map, cfg, "history_standard")
    main = _attach_features(_normalize(_load_log(root, cfg.main_log, cfg, sample_users), cfg), tag_map, cfg, "main_standard")

    vocab_lookup, action_map, actions, candidate_action_indices = _make_action_map(history, cfg)
    history = _apply_action_vocab(history, vocab_lookup, cfg)
    main = _apply_action_vocab(main, vocab_lookup, cfg)

    for name, frame in [("history_standard", history), ("main_standard", main)]:
        maybe_save_parquet(frame, output_dir / "processed" / f"{name}_processed.parquet")
    save_dataframe(action_map, output_dir / "processed" / "fixed_action_bucket_map.csv")
    vocab = pd.DataFrame({"action_index": np.arange(len(actions)), "action_bucket": actions})
    vocab["candidate_action"] = vocab["action_index"].isin(candidate_action_indices)
    save_dataframe(vocab, output_dir / "processed" / "action_vocabulary.csv")
    return PreparedLogs(history, main, action_map, actions, candidate_action_indices)

"""Construct split-consistent future-engagement targets for Exp3."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, ExperimentConfig
from utils import maybe_save_parquet, save_dataframe


def _engagement_value(frame: pd.DataFrame, cfg: ExperimentConfig) -> np.ndarray:
    weights = cfg.future_value_weights
    return (
        weights["long_view"] * frame[cfg.long_view_col].to_numpy(float)
        + weights["like"] * frame[cfg.like_col].to_numpy(float)
        + weights["comment"] * frame[cfg.comment_col].to_numpy(float)
        + weights["forward"] * frame[cfg.forward_col].to_numpy(float)
        + weights["follow"] * frame[cfg.follow_col].to_numpy(float)
    )


def _targets_for_one_user(
    source_group: pd.DataFrame,
    context_group: pd.DataFrame,
    cfg: ExperimentConfig,
) -> pd.DataFrame:
    """Compute every prespecified horizon for one user without cross-user context."""
    source = source_group.copy()
    context = context_group.sort_values(cfg.time_col, kind="stable")
    times = context[cfg.time_col].to_numpy(np.int64)
    values = context["_context_value"].to_numpy(float)
    cumulative = np.concatenate([[0.0], np.cumsum(values)])
    source_times = source[cfg.time_col].to_numpy(np.int64)
    left = np.searchsorted(times, source_times, side="right")
    user_end = int(times.max())

    for label, horizon in cfg.horizons_ms.items():
        right = np.searchsorted(times, source_times + int(horizon), side="right")
        future_value = cumulative[right] - cumulative[left]
        valid = (source_times + int(horizon)) <= user_end
        source[f"y_long_value_{label}"] = future_value
        source[f"y_long_value_log_{label}"] = np.log1p(future_value)
        source[f"valid_for_{label}"] = valid.astype(np.int8)
    return source


def add_future_engagement_targets(
    source_events: pd.DataFrame,
    output_dir: Path,
    prefix: str,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
    n_jobs: int = 1,
) -> pd.DataFrame:
    """Build same-user future-engagement targets within one standard-log split.

    The source and context stream are intentionally the same split. This avoids
    a history/main target-definition shift. ``n_jobs`` is effective only across
    user groups; chronological computation within a user remains serial.
    """
    source = source_events.copy().reset_index(drop=True)
    source["source_event_id"] = np.arange(len(source), dtype=np.int64)
    context = source_events.copy().reset_index(drop=True)
    context["_context_value"] = _engagement_value(context, cfg)

    source_groups = list(source.groupby(cfg.user_col, sort=False))
    context_groups = {
        user: group[[cfg.time_col, "_context_value"]].copy()
        for user, group in context.groupby(cfg.user_col, sort=False)
    }

    def run_group(item: tuple[object, pd.DataFrame]) -> pd.DataFrame:
        user, source_group = item
        context_group = context_groups.get(user)
        if context_group is None or context_group.empty:
            raise RuntimeError(f"Missing within-split context for user {user!r}.")
        return _targets_for_one_user(source_group, context_group, cfg)

    workers = max(1, int(n_jobs))
    if workers == 1 or len(source_groups) < 2:
        frames = [run_group(item) for item in source_groups]
    else:
        # NumPy searchsorted and cumulative operations dominate per-user work;
        # threads avoid copying multi-million-row data frames to subprocesses.
        with ThreadPoolExecutor(max_workers=workers) as executor:
            frames = list(executor.map(run_group, source_groups))

    out = (
        pd.concat(frames, ignore_index=True)
        .sort_values([cfg.user_col, cfg.time_col], kind="stable")
        .reset_index(drop=True)
    )

    summary_rows: list[dict[str, object]] = []
    for label in cfg.horizons_ms:
        valid = out[f"valid_for_{label}"].eq(1)
        values = out.loc[valid, f"y_long_value_log_{label}"]
        summary_rows.append({
            "horizon": label,
            "n_source_events": int(len(out)),
            "n_valid_source_events": int(valid.sum()),
            "right_censoring_rate": float(1.0 - valid.mean()) if len(out) else np.nan,
            "target_mean": float(values.mean()) if len(values) else np.nan,
            "target_sd": float(values.std(ddof=1)) if len(values) > 1 else np.nan,
            "context_streams": "main_standard_only" if prefix == "main_standard" else "history_standard_only",
        })
    save_dataframe(pd.DataFrame(summary_rows), output_dir / "summaries" / f"{prefix}_horizon_target_summary.csv")
    maybe_save_parquet(out, output_dir / "processed" / f"{prefix}_source_events_with_targets.parquet")
    return out

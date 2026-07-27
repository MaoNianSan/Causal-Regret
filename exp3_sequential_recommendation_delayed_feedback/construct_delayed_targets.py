"""Construct the 6h source-indexed target and deterministic pseudo-arrivals."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, ExperimentConfig, MS_HOUR
from utilities import save_frame, save_json, stable_uniform


def _engagement_value(frame: pd.DataFrame, cfg: ExperimentConfig) -> np.ndarray:
    w = cfg.future_value_weights
    return (
        w["long_view"] * frame[cfg.long_view_col].to_numpy(float)
        + w["like"] * frame[cfg.like_col].to_numpy(float)
        + w["comment"] * frame[cfg.comment_col].to_numpy(float)
        + w["forward"] * frame[cfg.forward_col].to_numpy(float)
        + w["follow"] * frame[cfg.follow_col].to_numpy(float)
    )


def _target_one_user(group: pd.DataFrame, split_end_ms: int, cfg: ExperimentConfig) -> pd.DataFrame:
    ordered = group.sort_values(cfg.time_col, kind="stable").copy()
    times = ordered[cfg.time_col].to_numpy(np.int64)
    values = _engagement_value(ordered, cfg)
    cumulative = np.concatenate([[0.0], np.cumsum(values)])
    # Frozen target contract: [t, t + horizon).  The source-time event is
    # included; an event exactly at the right endpoint is excluded.
    left = np.searchsorted(times, times, side="left")
    right = np.searchsorted(times, times + cfg.target_horizon_ms, side="left")
    future_value = cumulative[right] - cumulative[left]
    eligible = times + cfg.target_horizon_ms <= int(split_end_ms)
    ordered["target_window_end_time"] = times + cfg.target_horizon_ms
    ordered["is_target_eligible"] = eligible
    ordered["future_engagement_value_6h"] = np.where(eligible, future_value, np.nan)
    ordered["future_engagement_target_6h"] = np.where(eligible, np.log1p(future_value), np.nan)
    ordered["right_censoring_reason"] = np.where(eligible, "not_censored", "target_window_crosses_split_end")

    # Number of source windows that contain each outcome event. This is an audit
    # of the prespecified overlapping-window construction, not attribution.
    # For an outcome at time u, containing source windows satisfy
    # u - horizon < t <= u.  The strict lower bound follows from the
    # right-open endpoint of [t, t + horizon).  Use the full same-time block
    # so duplicate timestamps are handled symmetrically.
    start_positions = np.searchsorted(
        times, times - cfg.target_horizon_ms, side="right"
    )
    end_positions = np.searchsorted(times, times, side="right")
    ordered["source_windows_per_outcome_event"] = end_positions - start_positions
    return ordered


def add_delayed_targets(
    events: pd.DataFrame,
    split_end_ms: int,
    split_id: str,
    output_dir: Path,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
    n_jobs: int = 1,
) -> tuple[pd.DataFrame, dict[str, float]]:
    groups = list(events.groupby(cfg.user_col, sort=False))

    def task(item: tuple[object, pd.DataFrame]) -> pd.DataFrame:
        return _target_one_user(item[1], split_end_ms, cfg)

    if n_jobs > 1 and len(groups) > 1:
        with ThreadPoolExecutor(max_workers=max(1, n_jobs)) as executor:
            results = list(executor.map(task, groups))
    else:
        results = [task(item) for item in groups]
    targeted = pd.concat(results, ignore_index=True)
    targeted = targeted.sort_values([cfg.user_col, cfg.time_col], kind="stable").reset_index(drop=True)

    # Derive both arrays after the same final sort.  This prevents audit values
    # from being paired with engagement rows from a different user block.
    reuse_counts = (
        targeted["source_windows_per_outcome_event"].to_numpy(int)
        if len(targeted)
        else np.array([], dtype=int)
    )
    positive_context = _engagement_value(targeted, cfg) > 0
    positive_reuse = reuse_counts[positive_context] if reuse_counts.size else np.array([], dtype=int)
    events_per_user = targeted.groupby(cfg.user_col, observed=True).size().to_numpy(float)
    audit = {
        "split_id": split_id,
        "unique_user_count": int(targeted[cfg.user_col].nunique()),
        "source_event_count": int(len(targeted)),
        "eligible_source_event_count": int(targeted["is_target_eligible"].sum()),
        "positive_outcome_event_count": int(positive_reuse.size),
        "right_censoring_rate": float(1.0 - targeted["is_target_eligible"].mean()),
        "outcome_event_reuse_rate": float(np.mean(positive_reuse > 1)) if positive_reuse.size else 0.0,
        "mean_source_windows_per_outcome_event": float(np.mean(positive_reuse)) if positive_reuse.size else 0.0,
        "median_source_windows_per_outcome_event": float(np.median(positive_reuse)) if positive_reuse.size else 0.0,
        "p90_source_windows_per_outcome_event": float(np.quantile(positive_reuse, 0.90)) if positive_reuse.size else 0.0,
        "maximum_source_windows_per_outcome_event": float(np.max(positive_reuse)) if positive_reuse.size else 0.0,
        "mean_source_events_per_user": float(np.mean(events_per_user)) if events_per_user.size else 0.0,
        "p90_source_events_per_user": float(np.quantile(events_per_user, 0.90)) if events_per_user.size else 0.0,
    }
    save_frame(targeted, output_dir / "processed" / f"exp3_{split_id}_events_with_targets.parquet")
    save_json(audit, output_dir / "diagnostics" / f"exp3_{split_id}_target_audit.json")
    return targeted, audit


def attach_pseudo_arrivals_and_carriers(
    evaluation: pd.DataFrame,
    output_dir: Path,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = evaluation.copy()
    eligible_mask = out["is_target_eligible"].fillna(False).to_numpy(bool)
    delay_hours = np.full(len(out), np.nan, dtype=float)
    for index, event_id in enumerate(out["source_event_id"].astype(str)):
        if not eligible_mask[index]:
            continue
        uniform = stable_uniform(event_id, f"exp3-delay::{cfg.pseudo_delay_seed}")
        delay_hours[index] = cfg.pseudo_delay_min_hours + (
            cfg.pseudo_delay_max_hours - cfg.pseudo_delay_min_hours
        ) * uniform
    out["source_to_arrival_delay_hours"] = delay_hours
    out["feedback_arrival_time"] = np.where(
        eligible_mask,
        out[cfg.time_col].to_numpy(np.int64) + np.nan_to_num(delay_hours) * MS_HOUR,
        np.nan,
    )

    carrier_event_id = np.full(len(out), None, dtype=object)
    carrier_action_id = np.full(len(out), None, dtype=object)
    carrier_event_time = np.full(len(out), np.nan, dtype=float)
    carrier_status = np.full(len(out), "not_eligible", dtype=object)
    for _, group in out.groupby(cfg.user_col, sort=False):
        group = group.sort_values(cfg.time_col, kind="stable")
        idx = group.index.to_numpy()  # original DataFrame positions
        times = group[cfg.time_col].to_numpy(np.int64)
        arrivals = group["feedback_arrival_time"].to_numpy(float)

        finite = np.isfinite(arrivals)
        if not finite.any():
            continue

        # Vectorized: one searchsorted call per group instead of per row.
        carrier_locals = np.searchsorted(times, arrivals[finite], side="right") - 1
        valid = carrier_locals >= 0

        if valid.any():
            fin_idx = idx[finite][valid]
            car_pos = carrier_locals[valid]
            carrier_event_id[fin_idx] = group.iloc[car_pos]["source_event_id"].to_numpy()
            carrier_action_id[fin_idx] = group.iloc[car_pos]["action_id"].to_numpy()
            carrier_event_time[fin_idx] = group.iloc[car_pos][cfg.time_col].to_numpy(float)
            carrier_status[fin_idx] = "matched"

        unavailable = ~valid
        if unavailable.any():
            carrier_status[idx[finite][unavailable]] = "unavailable"
    out["carrier_event_id"] = carrier_event_id
    out["carrier_action_id"] = carrier_action_id
    out["carrier_event_time"] = carrier_event_time
    out["carrier_status"] = carrier_status
    out["source_to_carrier_lag_hours"] = (
        out["carrier_event_time"] - out[cfg.time_col]
    ) / MS_HOUR
    out["source_carrier_exact_match"] = out["carrier_event_id"].astype(str).eq(out["source_event_id"].astype(str))
    out["source_carrier_action_match"] = out["carrier_action_id"].astype(str).eq(out["action_id"].astype(str))

    eligible = out[out["is_target_eligible"]].copy()
    delay_bins = pd.cut(
        eligible["source_to_arrival_delay_hours"],
        bins=[6.0, 7.0, 8.0, 9.0, 10.000001],
        labels=["6-7h", "7-8h", "8-9h", "9-10h"],
        include_lowest=True,
        right=False,
    )
    eligible["delay_bin"] = delay_bins.astype(str)
    carrier_audit = (
        eligible.groupby("delay_bin", dropna=False)
        .agg(
            eligible_event_count=("source_event_id", "size"),
            carrier_available_rate=("carrier_status", lambda x: float(np.mean(x == "matched"))),
            exact_source_match_rate=("source_carrier_exact_match", "mean"),
            action_match_rate=("source_carrier_action_match", "mean"),
            lag_hours_p10=("source_to_carrier_lag_hours", lambda x: float(np.nanquantile(x, 0.10))),
            lag_hours_median=("source_to_carrier_lag_hours", "median"),
            lag_hours_p90=("source_to_carrier_lag_hours", lambda x: float(np.nanquantile(x, 0.90))),
            mean_source_to_carrier_lag_hours=("source_to_carrier_lag_hours", "mean"),
        )
        .reset_index()
    )
    action_audit = (
        eligible[eligible["action_id"].isin(eligible.loc[eligible["is_candidate_action"], "action_id"].unique())]
        .groupby("action_id", observed=True)
        .agg(
            eligible_event_count=("source_event_id", "size"),
            action_match_rate=("source_carrier_action_match", "mean"),
            exact_source_match_rate=("source_carrier_exact_match", "mean"),
            lag_hours_p10=("source_to_carrier_lag_hours", lambda x: float(np.nanquantile(x, 0.10))),
            lag_hours_median=("source_to_carrier_lag_hours", "median"),
            lag_hours_p90=("source_to_carrier_lag_hours", lambda x: float(np.nanquantile(x, 0.90))),
        )
        .reset_index()
    )
    if len(action_audit):
        action_audit["eligible_event_share"] = action_audit["eligible_event_count"] / float(action_audit["eligible_event_count"].sum())
    save_frame(out, output_dir / "processed" / "exp3_evaluation_events_with_arrivals.parquet")
    save_frame(carrier_audit, output_dir / "diagnostics" / "exp3_arrival_carrier_audit.csv")
    save_frame(action_audit, output_dir / "diagnostics" / "exp3_arrival_carrier_action_audit.csv")
    save_json(
        {
            "eligible_event_count": int(len(eligible)),
            "carrier_unavailable_rate": float(np.mean(eligible["carrier_status"] != "matched")) if len(eligible) else np.nan,
            "source_carrier_exact_match_rate": float(eligible["source_carrier_exact_match"].mean()) if len(eligible) else np.nan,
            "source_carrier_action_match_rate": float(eligible["source_carrier_action_match"].mean()) if len(eligible) else np.nan,
            "mean_source_to_arrival_delay_hours": float(eligible["source_to_arrival_delay_hours"].mean()) if len(eligible) else np.nan,
            "mean_source_to_carrier_lag_hours": float(eligible["source_to_carrier_lag_hours"].mean()) if len(eligible) else np.nan,
        },
        output_dir / "diagnostics" / "exp3_arrival_carrier_summary.json",
    )
    return out, carrier_audit

"""Sequential offline recoverability diagnostic for Experiment 3.

The unit ranked at a decision epoch is a history-defined action *category*.
Candidate masks are evaluation-support restrictions, not a platform candidate
set.  Consequently this is not an online recommender-policy evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, ExperimentConfig, MS_HOUR
from proxy_models import build_main_proxy_scores, decision_bin
from utils import save_dataframe, splitmix64_uniform, stable_uint64

METHOD_META: dict[str, dict[str, Any]] = {
    "arrival_time_naive": {
        "method_display_name": "Arrival-time carrier",
        "information_interface": "arrival_time_carrier",
        "reference_role": "none",
        "diagnostic_only": False,
        "deployable": False,
    },
    "source_labelled_empirical": {
        "method_display_name": "Source-labelled empirical",
        "information_interface": "source_labelled",
        "reference_role": "source_labelled_control",
        "diagnostic_only": True,
        "deployable": False,
    },
    "source_aware_reference": {
        "method_display_name": "Source-aware reference",
        "information_interface": "offline_source_target",
        "reference_role": "source_aware_reference",
        "diagnostic_only": False,
        "deployable": False,
    },
    "partial_source_label_q10": {
        "method_display_name": "Partial source labels, q=0.10",
        "information_interface": "partial_source_label",
        "reference_role": "none",
        "diagnostic_only": False,
        "deployable": False,
    },
    "partial_source_label_q30": {
        "method_display_name": "Partial source labels, q=0.30",
        "information_interface": "partial_source_label",
        "reference_role": "none",
        "diagnostic_only": False,
        "deployable": False,
    },
    "partial_source_label_q50": {
        "method_display_name": "Partial source labels, q=0.50",
        "information_interface": "partial_source_label",
        "reference_role": "none",
        "diagnostic_only": False,
        "deployable": False,
    },
    "history_mean_static": {
        "method_display_name": "History mean static",
        "information_interface": "history_target_mean_only",
        "reference_role": "diagnostic_control",
        "diagnostic_only": True,
        "deployable": False,
    },
    "short_term_ridge_proxy": {
        "method_display_name": "Short-term ridge proxy",
        "information_interface": "lagged_short_term_proxy",
        "reference_role": "none",
        "diagnostic_only": False,
        "deployable": False,
    },
    "history_ewma_ridge_proxy": {
        "method_display_name": "History EWMA ridge proxy",
        "information_interface": "history_plus_lagged_proxy",
        "reference_role": "none",
        "diagnostic_only": True,
        "deployable": False,
    },
    "short_term_composite_surrogate": {
        "method_display_name": "Short-term composite surrogate",
        "information_interface": "lagged_composite_proxy",
        "reference_role": "none",
        "diagnostic_only": False,
        "deployable": False,
    },
}


@dataclass
class ActionState:
    sums: np.ndarray
    counts: np.ndarray

    @classmethod
    def empty(cls, n_actions: int) -> "ActionState":
        return cls(np.zeros(n_actions, dtype=float), np.zeros(n_actions, dtype=float))

    def update(self, idx: np.ndarray, sums: np.ndarray, counts: np.ndarray) -> None:
        if len(idx) == 0:
            return
        np.add.at(self.sums, idx.astype(int), sums.astype(float))
        np.add.at(self.counts, idx.astype(int), counts.astype(float))

    def score(self, prior_mean: float, prior_count: float) -> np.ndarray:
        return (self.sums + prior_count * prior_mean) / (self.counts + prior_count)


@dataclass
class ArrivalDelta:
    source_idx: np.ndarray
    carrier_idx: np.ndarray
    outcomes: np.ndarray
    event_keys: np.ndarray
    user_idx: np.ndarray
    arrival_idx: np.ndarray


@dataclass
class PreparedCondition:
    condition: str
    actions: list[str]
    candidate_action_indices: np.ndarray
    bins: np.ndarray
    candidate_mask: np.ndarray  # fixed evaluation-support mask [B,A]
    reference_values: np.ndarray  # [B,A]
    prior_target_mean: float
    source_updates: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]]
    carrier_updates: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]]
    event_arrivals: dict[int, ArrivalDelta]
    arrival_bins: np.ndarray
    proxy_scores: dict[str, dict[int, np.ndarray]]
    proxy_prediction_rows: pd.DataFrame
    timeline: pd.DataFrame
    user_ids: np.ndarray
    user_cell_sums: np.ndarray
    user_cell_counts: np.ndarray
    user_source_update_sums: np.ndarray
    user_source_update_counts: np.ndarray
    user_carrier_update_sums: np.ndarray
    user_carrier_update_counts: np.ndarray
    proxy_coefficient_table: pd.DataFrame
    partial_update_cache: dict[tuple[float, int], tuple[np.ndarray, np.ndarray]] = (
        field(default_factory=dict)
    )


def _top_indices(
    scores: np.ndarray, candidates: np.ndarray, actions: list[str], k: int
) -> np.ndarray:
    order = sorted(candidates.tolist(), key=lambda i: (-float(scores[i]), actions[i]))
    return np.asarray(order[: min(k, len(order))], dtype=int)


def _same_user_current_action_at_arrival_indices(
    events: pd.DataFrame, cfg: ExperimentConfig, action_to_idx: dict[str, int]
) -> np.ndarray:
    """Assign an arrival to the most recent same-user exposure at or before arrival.

    Choosing the next exposure after arrival would use a future action and is
    temporally invalid.  The returned index is ``-1`` only when the user has no
    exposure before the pseudo-arrival.
    """
    result = np.full(len(events), -1, dtype=int)
    ordered = events.sort_values([cfg.user_col, cfg.time_col], kind="stable")
    for _, group in ordered.groupby(cfg.user_col, sort=False):
        row_idx = group.index.to_numpy(int)
        times = group[cfg.time_col].to_numpy(np.int64)
        action_idx = group["action_bucket"].astype(str).map(action_to_idx).to_numpy(int)
        arrival = group["arrival_time"].to_numpy(np.int64)
        pos = np.searchsorted(times, arrival, side="right") - 1
        valid = pos >= 0
        result[row_idx[valid]] = action_idx[pos[valid]]
    return result


def _construct_timeline(
    main_events: pd.DataFrame,
    condition: str,
    actions: list[str],
    cfg: ExperimentConfig,
    history_action_signal: dict[str, float] | None = None,
) -> pd.DataFrame:
    target_col = f"y_long_value_log_{cfg.primary_horizon}"
    out = (
        main_events.sort_values([cfg.time_col, cfg.user_col], kind="stable")
        .reset_index(drop=True)
        .copy()
    )
    action_to_idx = {a: i for i, a in enumerate(actions)}
    out["action_idx"] = out["action_bucket"].astype(str).map(action_to_idx).astype(int)
    out["source_time"] = out[cfg.time_col].astype(np.int64)
    out["source_bin"] = decision_bin(out["source_time"], cfg.sequential_bin_ms)
    out["source_outcome"] = (
        out[target_col]
        .where(out[f"valid_for_{cfg.primary_horizon}"].eq(1), np.nan)
        .astype(float)
    )
    out["event_key"] = stable_uint64(
        out[cfg.user_col].astype(str)
        + "|"
        + out[cfg.video_col].astype(str)
        + "|"
        + out[cfg.time_col].astype(str)
        + "|"
        + out.index.astype(str)
    )
    low = int(cfg.pseudo_delay_min_hours * MS_HOUR)
    width_ms = int((cfg.pseudo_delay_max_hours - cfg.pseudo_delay_min_hours) * MS_HOUR)
    hashes = out["event_key"].to_numpy(np.uint64)
    jitter = (hashes % np.uint64(max(1, width_ms + 1))).astype(np.int64)
    delay_pool = np.sort(low + jitter)
    fallback_signal = (
        float(np.nanmean(list(history_action_signal.values())))
        if history_action_signal
        else 0.0
    )
    action_signal = (
        out["action_bucket"]
        .astype(str)
        .map(history_action_signal or {})
        .fillna(fallback_signal)
        .to_numpy(float)
    )
    if condition == "independent_matched_delay_pool":
        order = np.argsort(hashes, kind="stable")
        mechanism = "stable_hash_assignment_independent_of_history_action_signal"
    elif condition == "action_value_coupled_matched_delay_pool":
        order = np.lexsort((hashes, action_signal))
        mechanism = "history_action_signal_rank_assignment"
    else:
        raise ValueError(condition)
    delay = np.empty(len(out), dtype=np.int64)
    delay[order] = delay_pool
    out["delay_condition"] = condition
    out["arrival_mechanism"] = mechanism
    out["pseudo_delay_ms"] = delay
    out["arrival_time"] = out["source_time"].to_numpy(np.int64) + delay
    out["arrival_bin"] = decision_bin(out["arrival_time"], cfg.sequential_bin_ms)
    out["action_value_signal"] = action_signal
    out["arrival_carrier_idx"] = _same_user_current_action_at_arrival_indices(
        out, cfg, action_to_idx
    )
    return out


def _evaluation_arrays(
    timeline: pd.DataFrame,
    actions: list[str],
    candidate_action_indices: np.ndarray,
    cfg: ExperimentConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, pd.DataFrame]:
    valid = timeline[timeline["source_outcome"].notna()].copy()
    valid = valid[valid["action_idx"].isin(candidate_action_indices)].copy()
    cells = (
        valid.groupby(["source_bin", "action_idx", "action_bucket"], dropna=False)
        .agg(n_events=("source_outcome", "size"), target_sum=("source_outcome", "sum"))
        .reset_index()
    )
    cells["source_aware_value"] = cells["target_sum"] / cells["n_events"]
    eligible = cells[cells["n_events"] >= cfg.sequential_min_cell_count].copy()
    counts_by_bin = eligible.groupby("source_bin")["action_idx"].nunique()
    keep_bins = counts_by_bin[counts_by_bin >= cfg.main_top_k].index.to_numpy(np.int64)
    eligible = eligible[eligible["source_bin"].isin(keep_bins)].copy()
    bins = np.sort(keep_bins)
    values = np.full((len(bins), len(actions)), np.nan, dtype=float)
    mask = np.zeros((len(bins), len(actions)), dtype=bool)
    bin_pos = {int(b): i for i, b in enumerate(bins)}
    for rec in eligible.itertuples(index=False):
        i = bin_pos[int(rec.source_bin)]
        values[i, int(rec.action_idx)] = float(rec.source_aware_value)
        mask[i, int(rec.action_idx)] = True
    return bins, mask, values, eligible


def _aggregated_updates(timeline: pd.DataFrame, n_actions: int) -> tuple[
    dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]],
    dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]],
    dict[int, ArrivalDelta],
]:
    valid = timeline[timeline["source_outcome"].notna()].copy()
    source_updates: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    carrier_updates: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    event_arrivals: dict[int, ArrivalDelta] = {}
    user_keys = np.sort(valid["_bootstrap_user_id"].unique())
    user_to_idx = {u: i for i, u in enumerate(user_keys)}
    arrival_bins = np.sort(valid["arrival_bin"].unique())
    arrival_to_idx = {int(b): i for i, b in enumerate(arrival_bins)}
    valid["_bootstrap_user_idx"] = (
        valid["_bootstrap_user_id"].map(user_to_idx).astype(int)
    )
    valid["_arrival_idx"] = valid["arrival_bin"].map(arrival_to_idx).astype(int)
    for arrival_bin, group in valid.groupby("arrival_bin", sort=False):
        b = int(arrival_bin)
        source = (
            group.groupby("action_idx")["source_outcome"]
            .agg(["sum", "count"])
            .reset_index()
        )
        source_updates[b] = (
            source["action_idx"].to_numpy(int),
            source["sum"].to_numpy(float),
            source["count"].to_numpy(float),
        )
        carrier_group = (
            group[group["arrival_carrier_idx"] >= 0]
            .groupby("arrival_carrier_idx")["source_outcome"]
            .agg(["sum", "count"])
            .reset_index()
        )
        carrier_updates[b] = (
            carrier_group["arrival_carrier_idx"].to_numpy(int),
            carrier_group["sum"].to_numpy(float),
            carrier_group["count"].to_numpy(float),
        )
        event_arrivals[b] = ArrivalDelta(
            source_idx=group["action_idx"].to_numpy(int),
            carrier_idx=group["arrival_carrier_idx"].to_numpy(int),
            outcomes=group["source_outcome"].to_numpy(float),
            event_keys=group["event_key"].to_numpy(np.uint64),
            user_idx=group["_bootstrap_user_idx"].to_numpy(int),
            arrival_idx=group["_arrival_idx"].to_numpy(int),
        )
    return source_updates, carrier_updates, event_arrivals


def _make_user_arrays(
    timeline: pd.DataFrame, bins: np.ndarray, n_actions: int, cfg: ExperimentConfig
) -> tuple[
    np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray
]:
    valid = timeline[timeline["source_outcome"].notna()].copy()
    users = np.sort(valid[cfg.user_col].astype(str).unique())
    user_to_idx = {u: i for i, u in enumerate(users)}
    valid["_bootstrap_user_id"] = valid[cfg.user_col].astype(str)
    valid["_bootstrap_user_idx"] = (
        valid["_bootstrap_user_id"].map(user_to_idx).astype(int)
    )
    arrival_bins = np.sort(valid["arrival_bin"].unique())
    arrival_to_idx = {int(b): i for i, b in enumerate(arrival_bins)}
    valid["_arrival_idx"] = valid["arrival_bin"].map(arrival_to_idx).astype(int)

    b_to_idx = {int(b): i for i, b in enumerate(bins)}
    in_eval = valid[valid["source_bin"].isin(bins)].copy()
    cell_sums = np.zeros((len(users), len(bins), n_actions), dtype=np.float32)
    cell_counts = np.zeros((len(users), len(bins), n_actions), dtype=np.float32)
    if not in_eval.empty:
        u = in_eval["_bootstrap_user_idx"].to_numpy(int)
        b = in_eval["source_bin"].map(b_to_idx).to_numpy(int)
        a = in_eval["action_idx"].to_numpy(int)
        np.add.at(cell_sums, (u, b, a), in_eval["source_outcome"].to_numpy(np.float32))
        np.add.at(cell_counts, (u, b, a), 1.0)

    source_sums = np.zeros((len(users), len(arrival_bins), n_actions), dtype=np.float32)
    source_counts = np.zeros(
        (len(users), len(arrival_bins), n_actions), dtype=np.float32
    )
    u = valid["_bootstrap_user_idx"].to_numpy(int)
    r = valid["_arrival_idx"].to_numpy(int)
    a = valid["action_idx"].to_numpy(int)
    y = valid["source_outcome"].to_numpy(np.float32)
    np.add.at(source_sums, (u, r, a), y)
    np.add.at(source_counts, (u, r, a), 1.0)

    carrier_sums = np.zeros_like(source_sums)
    carrier_counts = np.zeros_like(source_counts)
    carry = valid["arrival_carrier_idx"].to_numpy(int)
    ok = carry >= 0
    np.add.at(carrier_sums, (u[ok], r[ok], carry[ok]), y[ok])
    np.add.at(carrier_counts, (u[ok], r[ok], carry[ok]), 1.0)
    # Persist bootstrap index columns in timeline for partial-mask update construction.
    timeline.loc[valid.index, "_bootstrap_user_id"] = valid[
        "_bootstrap_user_id"
    ].to_numpy()
    timeline.loc[valid.index, "_bootstrap_user_idx"] = valid[
        "_bootstrap_user_idx"
    ].to_numpy()
    timeline.loc[valid.index, "_arrival_idx"] = valid["_arrival_idx"].to_numpy()
    return (
        users,
        cell_sums,
        cell_counts,
        source_sums,
        source_counts,
        carrier_sums,
        carrier_counts,
    )


def _attach_event_arrays(prepared: PreparedCondition, cfg: ExperimentConfig) -> None:
    # Event-level arrays need user and arrival indices assigned by _make_user_arrays.
    valid = prepared.timeline[prepared.timeline["source_outcome"].notna()].copy()
    prepared.event_arrivals.clear()
    for arrival_bin, group in valid.groupby("arrival_bin", sort=False):
        prepared.event_arrivals[int(arrival_bin)] = ArrivalDelta(
            source_idx=group["action_idx"].to_numpy(int),
            carrier_idx=group["arrival_carrier_idx"].to_numpy(int),
            outcomes=group["source_outcome"].to_numpy(float),
            event_keys=group["event_key"].to_numpy(np.uint64),
            user_idx=group["_bootstrap_user_idx"].to_numpy(int),
            arrival_idx=group["_arrival_idx"].to_numpy(int),
        )


def _partial_deltas(
    prepared: PreparedCondition, q: float, seeds: list[int]
) -> dict[int, dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]]]:
    n_actions = len(prepared.actions)
    out: dict[int, dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]]] = {}
    for seed in seeds:
        seed_updates: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for b, delta in prepared.event_arrivals.items():
            labelled = splitmix64_uniform(delta.event_keys, int(seed)) < float(q)
            idx = np.where(labelled, delta.source_idx, delta.carrier_idx)
            usable = idx >= 0
            sums = np.bincount(
                idx[usable], weights=delta.outcomes[usable], minlength=n_actions
            ).astype(float)
            counts = np.bincount(idx[usable], minlength=n_actions).astype(float)
            nz = np.flatnonzero(counts > 0)
            seed_updates[int(b)] = (nz, sums[nz], counts[nz])
        out[int(seed)] = seed_updates
    return out


def partial_user_update_arrays(
    prepared: PreparedCondition, q: float, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    """User-by-arrival-bin partial-label updates, cached per q/mask seed."""
    key = (float(q), int(seed))
    if key in prepared.partial_update_cache:
        return prepared.partial_update_cache[key]
    n_users = len(prepared.user_ids)
    n_arrivals = len(prepared.arrival_bins)
    n_actions = len(prepared.actions)
    sums = np.zeros((n_users, n_arrivals, n_actions), dtype=np.float32)
    counts = np.zeros_like(sums)
    for delta in prepared.event_arrivals.values():
        labelled = splitmix64_uniform(delta.event_keys, int(seed)) < float(q)
        idx = np.where(labelled, delta.source_idx, delta.carrier_idx)
        ok = idx >= 0
        np.add.at(
            sums,
            (delta.user_idx[ok], delta.arrival_idx[ok], idx[ok]),
            delta.outcomes[ok].astype(np.float32),
        )
        np.add.at(counts, (delta.user_idx[ok], delta.arrival_idx[ok], idx[ok]), 1.0)
    prepared.partial_update_cache[key] = (sums, counts)
    return sums, counts


def prepare_condition(
    main_events: pd.DataFrame,
    history_events: pd.DataFrame,
    actions: list[str],
    candidate_action_indices: np.ndarray,
    condition: str,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> PreparedCondition:
    history_target = f"y_long_value_log_{cfg.primary_horizon}"
    history_valid = history_events[
        history_events[f"valid_for_{cfg.primary_horizon}"].eq(1)
    ].copy()
    history_action_signal = (
        history_valid.groupby("action_bucket")[history_target].mean().to_dict()
    )
    prior_target_mean = float(history_valid[history_target].mean())
    timeline = _construct_timeline(
        main_events, condition, actions, cfg, history_action_signal
    )
    bins, candidate_mask, reference_values, _ = _evaluation_arrays(
        timeline, actions, candidate_action_indices, cfg
    )
    if len(bins) == 0:
        raise ValueError("No eligible source bins after applying support restriction.")
    users, cell_sums, cell_counts, source_us, source_uc, carrier_us, carrier_uc = (
        _make_user_arrays(timeline, bins, len(actions), cfg)
    )
    source_updates, carrier_updates, event_arrivals = _aggregated_updates(
        timeline, len(actions)
    )
    # Reattach because _make_user_arrays creates the canonical user/arrival indices.
    arrival_bins = np.sort(
        timeline.loc[timeline["source_outcome"].notna(), "arrival_bin"].unique()
    )
    scores, _, coefficient_table = build_main_proxy_scores(
        main_events, history_events, actions, bins, cfg
    )
    calibration_rows: list[dict[str, Any]] = []
    for method in ["short_term_ridge_proxy", "history_ewma_ridge_proxy"]:
        for i, b in enumerate(bins):
            candidates = np.flatnonzero(candidate_mask[i])
            for a in candidates:
                calibration_rows.append(
                    {
                        "method_id": method,
                        "decision_bin": int(b),
                        "bin_index": int(i),
                        "action_idx": int(a),
                        "action_bucket": actions[int(a)],
                        "predicted_long_value_log": float(
                            scores[method][int(b)][int(a)]
                        ),
                        "observed_long_value_log": float(reference_values[i, a]),
                    }
                )
    prep = PreparedCondition(
        condition=condition,
        actions=actions,
        candidate_action_indices=candidate_action_indices,
        bins=bins,
        candidate_mask=candidate_mask,
        reference_values=reference_values,
        prior_target_mean=prior_target_mean,
        source_updates=source_updates,
        carrier_updates=carrier_updates,
        event_arrivals=event_arrivals,
        arrival_bins=arrival_bins,
        proxy_scores=scores,
        proxy_prediction_rows=pd.DataFrame(calibration_rows),
        timeline=timeline,
        user_ids=users,
        user_cell_sums=cell_sums,
        user_cell_counts=cell_counts,
        user_source_update_sums=source_us,
        user_source_update_counts=source_uc,
        user_carrier_update_sums=carrier_us,
        user_carrier_update_counts=carrier_uc,
        proxy_coefficient_table=coefficient_table,
    )
    _attach_event_arrays(prep, cfg)
    return prep


def _update_state_over_interval(
    state: ActionState,
    updates: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]],
    last_decision: int | None,
    current_decision: int,
) -> None:
    for arrival_bin in sorted(updates):
        if arrival_bin < current_decision and (
            last_decision is None or arrival_bin >= last_decision
        ):
            idx, sm, cnt = updates[arrival_bin]
            state.update(idx, sm, cnt)


def _run_dynamic_trajectory(
    prepared: PreparedCondition,
    method: str,
    cfg: ExperimentConfig,
    mask_updates: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] | None = None,
    replication_id: int = 0,
) -> list[dict[str, Any]]:
    state = ActionState.empty(len(prepared.actions))
    rows: list[dict[str, Any]] = []
    bin_to_row = {int(b): i for i, b in enumerate(prepared.bins)}
    last_decision: int | None = None
    for b in prepared.bins:
        b = int(b)
        if method == "arrival_time_naive":
            updates = prepared.carrier_updates
        elif method == "source_labelled_empirical":
            updates = prepared.source_updates
        elif method.startswith("partial_source_label_q"):
            updates = mask_updates or {}
        else:
            raise ValueError(method)
        _update_state_over_interval(state, updates, last_decision, b)
        candidates = np.flatnonzero(prepared.candidate_mask[bin_to_row[b]])
        score = state.score(prepared.prior_target_mean, cfg.empirical_prior_count)
        top = _top_indices(score, candidates, prepared.actions, cfg.main_top_k)
        values = prepared.reference_values[bin_to_row[b]]
        oracle = _top_indices(values, candidates, prepared.actions, cfg.main_top_k)
        chosen, oracle_top = int(top[0]), int(oracle[0])
        rows.append(
            {
                "delay_condition": prepared.condition,
                "method_id": method,
                "replication_id": replication_id,
                "replication_kind": (
                    "label_mask"
                    if method.startswith("partial_")
                    else "fixed_trajectory"
                ),
                "decision_bin": b,
                "method_action_idx": chosen,
                "method_action": prepared.actions[chosen],
                "oracle_action_idx": oracle_top,
                "oracle_action": prepared.actions[oracle_top],
                "method_value": float(values[chosen]),
                "oracle_value": float(values[oracle_top]),
                "ranking_regret": float(values[oracle_top] - values[chosen]),
                "top_action_match": int(chosen == oracle_top),
                "selected_top_k_action_indices": "|".join(map(str, top.tolist())),
                "oracle_top_k_action_indices": "|".join(map(str, oracle.tolist())),
                "n_candidate_actions": int(len(candidates)),
            }
        )
        last_decision = b
    return rows


def _run_proxy_trajectory(
    prepared: PreparedCondition, method: str, cfg: ExperimentConfig
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for r, b in enumerate(prepared.bins):
        b = int(b)
        candidates = np.flatnonzero(prepared.candidate_mask[r])
        scores = prepared.proxy_scores[method][b]
        top = _top_indices(scores, candidates, prepared.actions, cfg.main_top_k)
        values = prepared.reference_values[r]
        oracle = _top_indices(values, candidates, prepared.actions, cfg.main_top_k)
        chosen, oracle_top = int(top[0]), int(oracle[0])
        rows.append(
            {
                "delay_condition": prepared.condition,
                "method_id": method,
                "replication_id": 0,
                "replication_kind": "fixed_history_fitted_proxy",
                "decision_bin": b,
                "method_action_idx": chosen,
                "method_action": prepared.actions[chosen],
                "oracle_action_idx": oracle_top,
                "oracle_action": prepared.actions[oracle_top],
                "method_value": float(values[chosen]),
                "oracle_value": float(values[oracle_top]),
                "ranking_regret": float(values[oracle_top] - values[chosen]),
                "top_action_match": int(chosen == oracle_top),
                "selected_top_k_action_indices": "|".join(map(str, top.tolist())),
                "oracle_top_k_action_indices": "|".join(map(str, oracle.tolist())),
                "n_candidate_actions": int(len(candidates)),
            }
        )
    return rows


def _source_reference_rows(
    prepared: PreparedCondition, cfg: ExperimentConfig
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for r, b in enumerate(prepared.bins):
        candidates = np.flatnonzero(prepared.candidate_mask[r])
        values = prepared.reference_values[r]
        oracle = _top_indices(values, candidates, prepared.actions, cfg.main_top_k)
        rows.append(
            {
                "delay_condition": prepared.condition,
                "method_id": "source_aware_reference",
                "replication_id": 0,
                "replication_kind": "offline_reference",
                "decision_bin": int(b),
                "method_action_idx": int(oracle[0]),
                "method_action": prepared.actions[int(oracle[0])],
                "oracle_action_idx": int(oracle[0]),
                "oracle_action": prepared.actions[int(oracle[0])],
                "method_value": float(values[int(oracle[0])]),
                "oracle_value": float(values[int(oracle[0])]),
                "ranking_regret": 0.0,
                "top_action_match": 1,
                "selected_top_k_action_indices": "|".join(map(str, oracle.tolist())),
                "oracle_top_k_action_indices": "|".join(map(str, oracle.tolist())),
                "n_candidate_actions": int(len(candidates)),
            }
        )
    return rows


def _metadata_columns(raw: pd.DataFrame) -> pd.DataFrame:
    meta = pd.DataFrame.from_dict(METHOD_META, orient="index").reset_index(
        names="method_id"
    )
    return raw.merge(meta, on="method_id", how="left")


def summary_from_raw(
    raw: pd.DataFrame, cfg: ExperimentConfig = DEFAULT_CONFIG
) -> pd.DataFrame:
    per_rep = (
        raw.groupby(
            ["delay_condition", "method_id", "replication_id", "replication_kind"],
            dropna=False,
        )
        .agg(
            n_decision_bins=("decision_bin", "size"),
            ranking_regret_per_time_bin=("ranking_regret", "mean"),
            top_action_match_rate=("top_action_match", "mean"),
            policy_value=("method_value", "mean"),
            oracle_value=("oracle_value", "mean"),
        )
        .reset_index()
    )
    out = (
        per_rep.groupby(
            ["delay_condition", "method_id", "replication_kind"], dropna=False
        )
        .agg(
            point_estimate=("ranking_regret_per_time_bin", "mean"),
            top_action_match_rate=("top_action_match_rate", "mean"),
            policy_value=("policy_value", "mean"),
            oracle_value=("oracle_value", "mean"),
            n_label_mask_trajectories=("replication_id", "nunique"),
            n_decision_bins=("n_decision_bins", "max"),
        )
        .reset_index()
    )
    return _metadata_columns(out)


def arrival_summary(prepared: PreparedCondition) -> pd.DataFrame:
    t = prepared.timeline
    rows = []
    for condition, g in t.groupby("delay_condition"):
        valid = g["source_outcome"].notna()
        delays = g.loc[valid, "pseudo_delay_ms"].to_numpy(float) / MS_HOUR
        corr = (
            np.corrcoef(
                g.loc[valid, "pseudo_delay_ms"].to_numpy(float),
                g.loc[valid, "action_value_signal"].to_numpy(float),
            )[0, 1]
            if valid.sum() > 2
            else np.nan
        )
        rows.append(
            {
                "delay_condition": condition,
                "n_arrival_messages": int(valid.sum()),
                "mean_delay_hours": float(np.mean(delays)),
                "sd_delay_hours": float(np.std(delays, ddof=1)),
                "p05_delay_hours": float(np.quantile(delays, 0.05)),
                "p50_delay_hours": float(np.quantile(delays, 0.5)),
                "p95_delay_hours": float(np.quantile(delays, 0.95)),
                "delay_history_action_signal_correlation": float(corr),
                "carrier_missing_rate": float(
                    (g.loc[valid, "arrival_carrier_idx"] < 0).mean()
                ),
                "arrival_mechanism": g["arrival_mechanism"].iloc[0],
                "carrier_rule": "most_recent_same_user_standard_exposure_at_or_before_arrival",
            }
        )
    return pd.DataFrame(rows)


def oracle_action_dynamics_summary(
    raw: pd.DataFrame, cfg: ExperimentConfig = DEFAULT_CONFIG
) -> pd.DataFrame:
    """Summarize how often the source-aware top action changes across bins.

    The table is a task-difficulty audit.  It prevents a stable category
    structure from being mistaken for short-term proxy recoverability.
    """
    reference = raw[
        (raw["method_id"] == "source_aware_reference")
        & (raw["delay_condition"] == cfg.primary_delay_condition)
    ].sort_values("decision_bin", kind="stable")
    if reference.empty:
        return pd.DataFrame()
    actions = reference["oracle_action"].astype(str).to_numpy()
    counts = pd.Series(actions).value_counts(dropna=False)
    n_bins = int(len(actions))
    switches = int(np.sum(actions[1:] != actions[:-1])) if n_bins > 1 else 0
    return pd.DataFrame(
        [
            {
                "delay_condition": cfg.primary_delay_condition,
                "n_decision_bins": n_bins,
                "oracle_top_action_unique_count": int(len(counts)),
                "oracle_top_action_switch_count": switches,
                "oracle_top_action_switch_rate": float(switches / max(1, n_bins - 1)),
                "oracle_top_action_share": float(counts.iloc[0] / n_bins),
                "most_common_oracle_action": str(counts.index[0]),
                "interpretation": "Task-difficulty audit; stable oracle categories can make history-only ranking competitive.",
            }
        ]
    )


def run_recoverability_experiment(
    main_events: pd.DataFrame,
    history_events: pd.DataFrame,
    actions: list[str],
    candidate_action_indices: np.ndarray,
    output_dir,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
    replication_seeds: list[int] | None = None,
) -> dict[str, Any]:
    seeds = list(replication_seeds or cfg.full_replication_seeds)
    all_raw: list[dict[str, Any]] = []
    preps: dict[str, PreparedCondition] = {}
    proxy_coefficients: list[pd.DataFrame] = []
    calibration_rows: list[pd.DataFrame] = []
    delays: list[pd.DataFrame] = []
    for condition in cfg.delay_conditions:
        prep = prepare_condition(
            main_events,
            history_events,
            actions,
            candidate_action_indices,
            condition,
            cfg,
        )
        preps[condition] = prep
        proxy_coefficients.append(
            prep.proxy_coefficient_table.assign(delay_condition=condition)
        )
        calibration_rows.append(
            prep.proxy_prediction_rows.assign(delay_condition=condition)
        )
        delays.append(arrival_summary(prep))
        all_raw.extend(_source_reference_rows(prep, cfg))
        for method in ["arrival_time_naive", "source_labelled_empirical"]:
            all_raw.extend(_run_dynamic_trajectory(prep, method, cfg))
        for method in [
            "history_mean_static",
            "short_term_ridge_proxy",
            "history_ewma_ridge_proxy",
            "short_term_composite_surrogate",
        ]:
            all_raw.extend(_run_proxy_trajectory(prep, method, cfg))
        for q in cfg.partial_label_rates:
            method = f"partial_source_label_q{int(round(q * 100)):02d}"
            updates = _partial_deltas(prep, q, seeds)
            for seed in seeds:
                all_raw.extend(
                    _run_dynamic_trajectory(
                        prep, method, cfg, updates[int(seed)], int(seed)
                    )
                )
        # Do not persist multi-GB timelines.  A per-condition compact audit is enough.
        audit = (
            prep.timeline[
                [
                    "source_event_id",
                    cfg.user_col,
                    "source_time",
                    "source_bin",
                    "arrival_time",
                    "arrival_bin",
                    "action_bucket",
                    "action_idx",
                    "arrival_carrier_idx",
                    "source_outcome",
                    "pseudo_delay_ms",
                    "delay_condition",
                ]
            ]
            .sample(n=min(200_000, len(prep.timeline)), random_state=20260622)
            .sort_values("source_time")
        )
        save_dataframe(
            audit,
            output_dir / "processed" / f"arrival_timeline_audit_sample_{condition}.csv",
        )
    raw = (
        _metadata_columns(pd.DataFrame(all_raw))
        .sort_values(["delay_condition", "method_id", "replication_id", "decision_bin"])
        .reset_index(drop=True)
    )
    summary = summary_from_raw(raw, cfg)
    save_dataframe(raw, output_dir / "raw" / "sequential_decision_raw.csv")
    save_dataframe(summary, output_dir / "summaries" / "sequential_method_summary.csv")
    save_dataframe(
        oracle_action_dynamics_summary(raw, cfg),
        output_dir / "summaries" / "oracle_action_dynamics_summary.csv",
    )
    save_dataframe(
        pd.concat(delays, ignore_index=True),
        output_dir / "summaries" / "arrival_mechanism_summary.csv",
    )
    save_dataframe(
        pd.concat(proxy_coefficients, ignore_index=True),
        output_dir / "tables" / "proxy_ridge_coefficients.csv",
    )
    save_dataframe(
        pd.concat(calibration_rows, ignore_index=True),
        output_dir / "raw" / "proxy_calibration_cells_raw.csv",
    )
    save_dataframe(
        pd.DataFrame.from_dict(METHOD_META, orient="index").reset_index(
            names="method_id"
        ),
        output_dir / "metadata" / "method_information_contract.csv",
    )
    return {"raw": raw, "summary": summary, "prepared": preps}

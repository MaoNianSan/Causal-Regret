"""User-cluster uncertainty summaries for Exp3.

The procedure resamples users while replaying empirical arrival/source-label
updates. Partial-label routes additionally sample one event-level mask trajectory
with replacement from the prespecified finite mask bank (3 trajectories in fast,
30 in full). History-fitted proxy coefficients and support masks remain fixed.
This is a conditional diagnostic interval, not an OPE confidence interval.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, ExperimentConfig
from recoverability import METHOD_META, PreparedCondition, ActionState, partial_user_update_arrays
from utils import percentile_ci, save_dataframe


def _parse_topk(text: str, k: int) -> np.ndarray:
    if not isinstance(text, str) or not text:
        return np.empty(0, dtype=int)
    return np.asarray([int(x) for x in text.split("|") if x != ""][:k], dtype=int)


def _fixed_action_maps(raw: pd.DataFrame, prepared: PreparedCondition, cfg: ExperimentConfig) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    b_to_idx = {int(b): i for i, b in enumerate(prepared.bins)}
    result: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    fixed_methods = ["history_mean_static", "short_term_ridge_proxy", "history_ewma_ridge_proxy", "short_term_composite_surrogate"]
    subset = raw[(raw["delay_condition"] == prepared.condition) & raw["method_id"].isin(fixed_methods)]
    for method, group in subset.groupby("method_id", sort=False):
        chosen = np.full(len(prepared.bins), -1, dtype=int)
        topk = np.full((len(prepared.bins), cfg.main_top_k), -1, dtype=int)
        for rec in group.itertuples(index=False):
            j = b_to_idx.get(int(rec.decision_bin))
            if j is None:
                continue
            chosen[j] = int(rec.method_action_idx)
            parsed = _parse_topk(rec.selected_top_k_action_indices, cfg.main_top_k)
            topk[j, :len(parsed)] = parsed
        result[method] = (chosen, topk)
    return result


def _top_indices(scores: np.ndarray, candidates: np.ndarray, actions: list[str], k: int) -> np.ndarray:
    order = sorted(candidates.tolist(), key=lambda i: (-float(scores[i]), actions[i]))
    return np.asarray(order[:min(k, len(order))], dtype=int)


def _reference_actions(values: np.ndarray, mask: np.ndarray, actions: list[str], cfg: ExperimentConfig) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    b_count = values.shape[0]
    top1 = np.full(b_count, -1, dtype=int)
    topk = np.full((b_count, cfg.main_top_k), -1, dtype=int)
    oracle_val = np.full(b_count, np.nan, dtype=float)
    for b in range(b_count):
        cand = np.flatnonzero(mask[b] & np.isfinite(values[b]))
        if len(cand) == 0:
            continue
        order = _top_indices(values[b], cand, actions, cfg.main_top_k)
        top1[b] = int(order[0])
        topk[b, :len(order)] = order
        oracle_val[b] = float(values[b, top1[b]])
    return top1, topk, oracle_val


def _replay_dynamic_actions(update_sums: np.ndarray, update_counts: np.ndarray, prepared: PreparedCondition, values: np.ndarray, cfg: ExperimentConfig) -> tuple[np.ndarray, np.ndarray]:
    """Replay a route with user-resampled arrival-bin update arrays."""
    chosen = np.full(len(prepared.bins), -1, dtype=int)
    topk = np.full((len(prepared.bins), cfg.main_top_k), -1, dtype=int)
    state = ActionState.empty(len(prepared.actions))
    last_decision: int | None = None
    for bi, b in enumerate(prepared.bins):
        b = int(b)
        eligible_arrivals = (prepared.arrival_bins < b)
        if last_decision is not None:
            eligible_arrivals &= prepared.arrival_bins >= int(last_decision)
        for ai in np.flatnonzero(eligible_arrivals):
            idx = np.flatnonzero(update_counts[ai] > 0)
            if len(idx):
                state.update(idx, update_sums[ai, idx], update_counts[ai, idx])
        candidates = np.flatnonzero(prepared.candidate_mask[bi] & np.isfinite(values[bi]))
        if len(candidates):
            score = state.score(prepared.prior_target_mean, cfg.empirical_prior_count)
            ordered = _top_indices(score, candidates, prepared.actions, cfg.main_top_k)
            chosen[bi] = int(ordered[0])
            topk[bi, :len(ordered)] = ordered
        last_decision = b
    return chosen, topk


def _metric_from_actions(values: np.ndarray, candidate_mask: np.ndarray, actions: list[str], chosen: np.ndarray, selected_topk: np.ndarray, cfg: ExperimentConfig) -> tuple[float, float, float]:
    oracle_top1, oracle_topk, oracle_value = _reference_actions(values, candidate_mask, actions, cfg)
    selected_value = np.full(len(chosen), np.nan, dtype=float)
    valid = (chosen >= 0) & (oracle_top1 >= 0)
    valid[valid] &= np.isfinite(values[np.arange(len(chosen))[valid], chosen[valid]])
    selected_value[valid] = values[np.arange(len(chosen))[valid], chosen[valid]]
    regrets = np.where(valid, oracle_value - selected_value, np.nan)
    match = np.where(valid, (chosen == oracle_top1).astype(float), np.nan)
    overlap = np.full(len(chosen), np.nan, dtype=float)
    for b in np.flatnonzero(valid):
        p = set(selected_topk[b][selected_topk[b] >= 0].tolist())
        o = set(oracle_topk[b][oracle_topk[b] >= 0].tolist())
        denom = max(1, min(cfg.main_top_k, int(np.sum(candidate_mask[b] & np.isfinite(values[b])))))
        overlap[b] = len(p & o) / denom
    return float(np.nanmean(regrets)), float(np.nanmean(match)), float(np.nanmean(overlap))


def _calibration_rows(sums: np.ndarray, counts: np.ndarray, calibration: pd.DataFrame, cfg: ExperimentConfig, bootstrap_rep: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if calibration.empty:
        return rows
    for method, frame in calibration.groupby("method_id", sort=False):
        work = frame.copy()
        try:
            work["decile"] = pd.qcut(work["predicted_long_value_log"].rank(method="first"), 10, labels=False, duplicates="drop")
        except ValueError:
            work["decile"] = 0
        for decile, group in work.groupby("decile", sort=True):
            bi = group["bin_index"].to_numpy(int)
            ai = group["action_idx"].to_numpy(int)
            total_sum = float(sums[bi, ai].sum())
            total_count = float(counts[bi, ai].sum())
            rows.append({
                "bootstrap_rep": bootstrap_rep, "method_id": method, "decile": int(decile),
                "mean_predicted_long_value_log": float(group["predicted_long_value_log"].mean()),
                "mean_observed_long_value_log": total_sum / total_count if total_count > 0 else np.nan,
            })
    return rows


def _weighted_arrays(weights: np.ndarray, arr: np.ndarray) -> np.ndarray:
    n_users = arr.shape[0]
    return (weights @ arr.reshape(n_users, -1)).reshape(arr.shape[1:])


def run_user_bootstrap(
    raw: pd.DataFrame,
    prepared: dict[str, PreparedCondition],
    output_dir,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
    n_bootstrap: int | None = None,
    seed: int = 20260622,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    n_bootstrap = int(n_bootstrap or cfg.full_bootstrap_n)
    rng = np.random.default_rng(seed)
    all_rows: list[dict[str, Any]] = []
    calibration_rows: list[dict[str, Any]] = []

    # The two pseudo-arrival conditions share the same main users.  Reusing the
    # same user-resampling weights by bootstrap replicate makes the resulting
    # coupled-minus-independent contrast a paired user-cluster diagnostic.
    first_prep = next(iter(prepared.values()))
    common_n_users = len(first_prep.user_ids)
    if any(len(prep.user_ids) != common_n_users or not np.array_equal(prep.user_ids, first_prep.user_ids) for prep in prepared.values()):
        raise ValueError("Mechanism contrast requires identical ordered user sets across conditions.")
    shared_bootstrap_weights = [
        rng.multinomial(common_n_users, np.full(common_n_users, 1.0 / common_n_users)).astype(np.float64)
        for _ in range(n_bootstrap)
    ]

    for condition, prep in prepared.items():
        n_users = len(prep.user_ids)
        if n_users < 2:
            raise ValueError("User bootstrap requires at least two users.")
        fixed_maps = _fixed_action_maps(raw, prep, cfg)
        partial_methods = {f"partial_source_label_q{int(round(q*100)):02d}": q for q in cfg.partial_label_rates}
        available_seeds = np.asarray(cfg.fast_replication_seeds if len(raw[raw["delay_condition"] == condition]["replication_id"].unique()) <= len(cfg.fast_replication_seeds)+5 else cfg.full_replication_seeds, dtype=int)
        # Exact available seeds from raw partial routes, which supports custom configs.
        route_seeds = raw[(raw["delay_condition"] == condition) & raw["method_id"].str.startswith("partial_source_label_", na=False)]["replication_id"].unique()
        if len(route_seeds):
            available_seeds = np.sort(route_seeds.astype(int))

        for rep in range(n_bootstrap):
            weights = shared_bootstrap_weights[rep]
            cell_sums = _weighted_arrays(weights, prep.user_cell_sums)
            cell_counts = _weighted_arrays(weights, prep.user_cell_counts)
            values = np.divide(cell_sums, cell_counts, out=np.full_like(cell_sums, np.nan, dtype=float), where=cell_counts > 0)
            oracle_top1, oracle_topk, _ = _reference_actions(values, prep.candidate_mask, prep.actions, cfg)
            # Reference is defined conditional on each bootstrap target table.
            all_rows.append({"bootstrap_rep": rep, "delay_condition": condition, "method_id": "source_aware_reference", "ranking_regret_per_time_bin": 0.0, "top_action_match_rate": 1.0, "top_k_overlap_with_source_aware_reference": 1.0})

            # Empirical dynamic routes replay state paths under resampled user outcomes.
            dynamic_specs = {
                "arrival_time_naive": (prep.user_carrier_update_sums, prep.user_carrier_update_counts),
                "source_labelled_empirical": (prep.user_source_update_sums, prep.user_source_update_counts),
            }
            for method, (u_sums, u_counts) in dynamic_specs.items():
                sums = _weighted_arrays(weights, u_sums)
                counts = _weighted_arrays(weights, u_counts)
                chosen, topk = _replay_dynamic_actions(sums, counts, prep, values, cfg)
                regret, match, overlap = _metric_from_actions(values, prep.candidate_mask, prep.actions, chosen, topk, cfg)
                all_rows.append({"bootstrap_rep": rep, "delay_condition": condition, "method_id": method, "ranking_regret_per_time_bin": regret, "top_action_match_rate": match, "top_k_overlap_with_source_aware_reference": overlap})

            # Partial routes pair the user resample with one pre-generated, independent
            # event-level mask trajectory from the finite mask bank. The bank size is
            # 3 in fast mode and 30 in full mode; this avoids an infeasible nested
            # re-scan of every source event for each of 1,000 bootstrap draws.
            for method, q in partial_methods.items():
                mask_seed = int(rng.choice(available_seeds))
                u_sums, u_counts = partial_user_update_arrays(prep, float(q), mask_seed)
                sums = _weighted_arrays(weights, u_sums)
                counts = _weighted_arrays(weights, u_counts)
                chosen, topk = _replay_dynamic_actions(sums, counts, prep, values, cfg)
                regret, match, overlap = _metric_from_actions(values, prep.candidate_mask, prep.actions, chosen, topk, cfg)
                all_rows.append({"bootstrap_rep": rep, "delay_condition": condition, "method_id": method, "ranking_regret_per_time_bin": regret, "top_action_match_rate": match, "top_k_overlap_with_source_aware_reference": overlap, "label_mask_seed": mask_seed})

            # Ridge coefficients and proxy score paths are history-fitted and held fixed.
            for method, (chosen, topk) in fixed_maps.items():
                regret, match, overlap = _metric_from_actions(values, prep.candidate_mask, prep.actions, chosen, topk, cfg)
                all_rows.append({"bootstrap_rep": rep, "delay_condition": condition, "method_id": method, "ranking_regret_per_time_bin": regret, "top_action_match_rate": match, "top_k_overlap_with_source_aware_reference": overlap})
            for cal_row in _calibration_rows(cell_sums, cell_counts, prep.proxy_prediction_rows, cfg, rep):
                cal_row["delay_condition"] = condition
                calibration_rows.append(cal_row)

    draws = pd.DataFrame(all_rows)
    if draws.empty:
        raise RuntimeError("Bootstrap produced no draws.")
    raw_point = raw.groupby(["delay_condition", "method_id"], sort=False).agg(
        ranking_regret_per_time_bin=("ranking_regret", "mean"),
        top_action_match_rate=("top_action_match", "mean"),
    ).reset_index().set_index(["delay_condition", "method_id"])
    summary_rows = []
    for (condition, method), group in draws.groupby(["delay_condition", "method_id"], sort=False):
        lo, hi = percentile_ci(group["ranking_regret_per_time_bin"], cfg.ci_level)
        olo, ohi = percentile_ci(group["top_k_overlap_with_source_aware_reference"], cfg.ci_level)
        mlo, mhi = percentile_ci(group["top_action_match_rate"], cfg.ci_level)
        raw_rec = raw_point.loc[(condition, method)]
        summary_rows.append({
            "experiment_id": "exp3_long_term_recoverability", "delay_condition": condition, "method_id": method,
            **METHOD_META.get(method, {}), "metric_id": "ranking_regret_per_time_bin",
            "point_estimate": float(raw_rec["ranking_regret_per_time_bin"]), "ci_lower": lo, "ci_upper": hi,
            "top_k_overlap_with_source_aware_reference": float(group["top_k_overlap_with_source_aware_reference"].mean()), "top_k_overlap_ci_lower": olo, "top_k_overlap_ci_upper": ohi,
            "top_action_match_rate": float(raw_rec["top_action_match_rate"]), "top_action_match_ci_lower": mlo, "top_action_match_ci_upper": mhi,
            "ci_level": cfg.ci_level,
            "uncertainty_unit": "user_cluster_resampling_of_empirical_update_routes_with_fixed_support_and_history_fitted_proxy_scores",
            "label_mask_uncertainty": f"partial routes pair each user bootstrap draw with one trajectory sampled from a finite bank of {len(available_seeds)} independent event-level source-label masks",
            "n_bootstrap": n_bootstrap,
        })
    summary = pd.DataFrame(summary_rows)

    effects_rows = []
    for condition, group in draws.groupby("delay_condition", sort=False):
        base = group[group["method_id"] == "arrival_time_naive"][["bootstrap_rep", "ranking_regret_per_time_bin"]].rename(columns={"ranking_regret_per_time_bin": "base"})
        for method, target in group.groupby("method_id", sort=False):
            if method == "arrival_time_naive":
                continue
            merged = target[["bootstrap_rep", "ranking_regret_per_time_bin"]].merge(base, on="bootstrap_rep", how="inner")
            reduction = merged["base"] - merged["ranking_regret_per_time_bin"]
            lo, hi = percentile_ci(reduction, cfg.ci_level)
            raw_base = float(raw_point.loc[(condition, "arrival_time_naive"), "ranking_regret_per_time_bin"])
            raw_target = float(raw_point.loc[(condition, method), "ranking_regret_per_time_bin"])
            effects_rows.append({"delay_condition": condition, "method_id": method, "metric_id": "ranking_regret_reduction_vs_arrival_time", "point_estimate": raw_base - raw_target, "ci_lower": lo, "ci_upper": hi, "ci_level": cfg.ci_level, "n_bootstrap": n_bootstrap})
    effects = pd.DataFrame(effects_rows)

    # Paired static-control comparison: positive values mean the named route
    # has lower regret than the history-only category-mean control. This tests
    # incremental decision-level value beyond stable history-category ranking.
    static_effect_rows = []
    static_control = "history_mean_static"
    for condition, group in draws.groupby("delay_condition", sort=False):
        base = group[group["method_id"] == static_control][["bootstrap_rep", "ranking_regret_per_time_bin"]].rename(columns={"ranking_regret_per_time_bin": "history_mean"})
        if base.empty:
            continue
        for method, target in group.groupby("method_id", sort=False):
            if method == static_control:
                continue
            merged = target[["bootstrap_rep", "ranking_regret_per_time_bin"]].merge(base, on="bootstrap_rep", how="inner")
            if merged.empty:
                continue
            reduction = merged["history_mean"] - merged["ranking_regret_per_time_bin"]
            lo, hi = percentile_ci(reduction, cfg.ci_level)
            raw_base = float(raw_point.loc[(condition, static_control), "ranking_regret_per_time_bin"])
            raw_target = float(raw_point.loc[(condition, method), "ranking_regret_per_time_bin"])
            static_effect_rows.append({
                "delay_condition": condition,
                "method_id": method,
                "comparator_method_id": static_control,
                "metric_id": "ranking_regret_reduction_vs_history_mean_static",
                "point_estimate": raw_base - raw_target,
                "ci_lower": lo,
                "ci_upper": hi,
                "ci_level": cfg.ci_level,
                "n_bootstrap": n_bootstrap,
                "uncertainty_unit": "paired_user_cluster_bootstrap_same_user_weights_with_fixed_history_fitted_proxy_scores",
                "interpretation": "Positive values favor the named route over the history-only static control; intervals spanning zero do not establish incremental dynamic proxy value.",
            })
    static_effects = pd.DataFrame(static_effect_rows)

    # Paired mechanism contrast: positive values mean the coupled pseudo-arrival
    # mechanism yields larger regret than the independent mechanism.  Since each
    # bootstrap replicate uses the same resampled users across conditions, the
    # interval reflects within-replicate mechanism differences.
    contrast_rows = []
    independent = "independent_matched_delay_pool"
    coupled = "action_value_coupled_matched_delay_pool"
    for method in sorted(draws["method_id"].dropna().unique()):
        left = draws[(draws["delay_condition"] == coupled) & (draws["method_id"] == method)][["bootstrap_rep", "ranking_regret_per_time_bin"]].rename(columns={"ranking_regret_per_time_bin": "coupled"})
        right = draws[(draws["delay_condition"] == independent) & (draws["method_id"] == method)][["bootstrap_rep", "ranking_regret_per_time_bin"]].rename(columns={"ranking_regret_per_time_bin": "independent"})
        paired = left.merge(right, on="bootstrap_rep", how="inner")
        if paired.empty:
            continue
        delta = paired["coupled"] - paired["independent"]
        raw_left = raw_point.loc[(coupled, method), "ranking_regret_per_time_bin"] if (coupled, method) in raw_point.index else np.nan
        raw_right = raw_point.loc[(independent, method), "ranking_regret_per_time_bin"] if (independent, method) in raw_point.index else np.nan
        lo, hi = percentile_ci(delta, cfg.ci_level)
        contrast_rows.append({
            "method_id": method,
            "metric_id": "ranking_regret_coupled_minus_independent",
            "point_estimate": float(raw_left - raw_right),
            "ci_lower": lo,
            "ci_upper": hi,
            "ci_level": cfg.ci_level,
            "n_bootstrap": n_bootstrap,
            "uncertainty_unit": "paired_user_cluster_bootstrap_same_user_weights_across_mechanisms",
        })
    mechanism_contrast = pd.DataFrame(contrast_rows)

    calibration = pd.DataFrame(calibration_rows)
    if not calibration.empty:
        calibration_summary = calibration.groupby(["delay_condition", "method_id", "decile", "mean_predicted_long_value_log"], sort=False).agg(
            mean_observed_long_value_log=("mean_observed_long_value_log", "mean"),
            ci_lower=("mean_observed_long_value_log", lambda x: percentile_ci(x, cfg.ci_level)[0]),
            ci_upper=("mean_observed_long_value_log", lambda x: percentile_ci(x, cfg.ci_level)[1]),
            n_bootstrap=("bootstrap_rep", "nunique"),
        ).reset_index()
    else:
        calibration_summary = pd.DataFrame()

    save_dataframe(draws, output_dir / "raw" / "user_bootstrap_draws.csv")
    save_dataframe(summary, output_dir / "summaries" / "user_bootstrap_metric_summary.csv")
    save_dataframe(effects, output_dir / "summaries" / "paired_effect_vs_arrival_time.csv")
    save_dataframe(static_effects, output_dir / "summaries" / "paired_effect_vs_history_mean_static.csv")
    save_dataframe(mechanism_contrast, output_dir / "summaries" / "paired_mechanism_contrast.csv")
    save_dataframe(calibration, output_dir / "raw" / "proxy_calibration_bootstrap_draws.csv")
    save_dataframe(calibration_summary, output_dir / "summaries" / "proxy_calibration_summary.csv")
    return summary, effects, calibration_summary

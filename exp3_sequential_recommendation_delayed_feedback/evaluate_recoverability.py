"""Cross-fitted score, action-gap, and ranking recovery estimands."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from audit_design import AuditDesign, summarize_support_table
from config import DEFAULT_CONFIG, ExperimentConfig
from evaluation_artifacts import EvaluationArrays, MetricResult
from utilities import deterministic_tie_argmax, spearman_correlation


ROUTE_META = {
    "arrival_carrier": {
        "route_display_name": "Arrival carrier",
        "route_role": "baseline",
        "is_deployable": True,
        "uses_future_outcome": False,
        "uses_source_identity": False,
    },
    "history_mean_control": {
        "route_display_name": "Historical mean",
        "route_role": "control",
        "is_deployable": True,
        "uses_future_outcome": False,
        "uses_source_identity": False,
    },
    "ridge_proxy": {
        "route_display_name": "Ridge proxy",
        "route_role": "primary_proxy",
        "is_deployable": True,
        "uses_future_outcome": False,
        "uses_source_identity": False,
    },
}



def _aggregate_user_arrays(
    arrays: EvaluationArrays,
    user_weights: np.ndarray,
    group_count: int,
    fold_count: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    d_count = len(arrays.calendar_days)
    a_count = len(arrays.candidate_actions)
    shape = (d_count, group_count, fold_count, a_count)
    source_sum = np.zeros(shape, dtype=float)
    source_count = np.zeros(shape, dtype=float)
    arrival_sum = np.zeros(shape, dtype=float)
    arrival_count = np.zeros(shape, dtype=float)
    for group_id in range(group_count):
        for fold_id in range(fold_count):
            mask = (arrays.user_group_ids == group_id) & (arrays.reference_fold_ids == fold_id)
            if not mask.any():
                continue
            weights = user_weights[mask]
            source_sum[:, group_id, fold_id] = np.tensordot(weights, arrays.source_target_sum[mask], axes=(0, 0))
            source_count[:, group_id, fold_id] = np.tensordot(weights, arrays.source_target_count[mask], axes=(0, 0))
            arrival_sum[:, group_id, fold_id] = np.tensordot(weights, arrays.arrival_target_sum[mask], axes=(0, 0))
            arrival_count[:, group_id, fold_id] = np.tensordot(weights, arrays.arrival_target_count[mask], axes=(0, 0))
    return source_sum, source_count, arrival_sum, arrival_count


def _assign_deciles(cell_table: pd.DataFrame) -> dict[tuple[str, str, int, str], int]:
    membership: dict[tuple[str, str, int, str], int] = {}
    for route_id in ("history_mean_control", "ridge_proxy"):
        route = cell_table[cell_table["route_id"] == route_id].copy()
        if route.empty:
            continue
        ranks = route["route_score"].rank(method="first")
        bins = pd.qcut(ranks, q=min(10, len(route)), labels=False, duplicates="drop")
        for row, decile in zip(route.itertuples(), bins):
            membership[(route_id, str(row.calendar_day), int(row.user_group_id), str(row.action_id))] = int(decile) + 1
    return membership


def compute_metrics(
    arrays: EvaluationArrays,
    design: AuditDesign,
    user_weights: np.ndarray | None = None,
    decile_membership: dict[tuple[str, str, int, str], int] | None = None,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> MetricResult:
    if user_weights is None:
        user_weights = np.ones(len(arrays.user_ids), dtype=float)
    user_weights = np.asarray(user_weights, dtype=float)
    if user_weights.shape != (len(arrays.user_ids),):
        raise ValueError("user_weights has the wrong shape")
    source_sum, source_count, arrival_sum, arrival_count = _aggregate_user_arrays(
        arrays, user_weights, design.user_group_count, cfg.reference_fold_count
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        observed_mean = source_sum / source_count
    arrival_scores = np.empty_like(arrival_sum)
    for group_id in range(design.user_group_count):
        prior = arrays.history_scores[group_id]
        arrival_scores[:, group_id] = (
            arrival_sum[:, group_id]
            + cfg.history_prior_count * prior[None, None, :]
        ) / (arrival_count[:, group_id] + cfg.history_prior_count)

    route_score_arrays = {
        "arrival_carrier": arrival_scores,
        "history_mean_control": np.repeat(
            arrays.fixed_route_scores["history_mean_control"][:, :, None, :],
            cfg.reference_fold_count,
            axis=2,
        ),
        "ridge_proxy": np.repeat(
            arrays.fixed_route_scores["ridge_proxy"][:, :, None, :],
            cfg.reference_fold_count,
            axis=2,
        ),
    }
    action_order = np.arange(len(arrays.candidate_actions), dtype=int)
    unit_rows: list[dict[str, Any]] = []
    cell_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    support_margin_rows: list[dict[str, Any]] = []

    for d, day in enumerate(arrays.calendar_days):
        for group_id in range(design.user_group_count):
            common_supported = np.all(
                source_count[d, group_id] >= design.support_min_events_per_fold,
                axis=0,
            )
            supported_indices = np.flatnonzero(common_supported)
            action_coverage = len(supported_indices) / len(arrays.candidate_actions)
            pair_coverage = (
                (len(supported_indices) - 1) / (len(arrays.candidate_actions) - 1)
                if len(supported_indices) >= 2 and len(arrays.candidate_actions) > 1
                else 0.0
            )
            valid_unit = len(supported_indices) >= 2
            audit_unit_id = f"{day}__group_{group_id:02d}"
            for action_idx, action_id in enumerate(arrays.candidate_actions):
                fold_counts = source_count[d, group_id, :, action_idx].astype(float)
                minimum_fold_count = float(np.min(fold_counts))
                support_margin_rows.append(
                    {
                        "calendar_day": day,
                        "user_group_id": group_id,
                        "audit_unit_id": audit_unit_id,
                        "action_id": action_id,
                        "fold_0_count": float(fold_counts[0]),
                        "fold_1_count": float(fold_counts[1]),
                        "minimum_fold_count": minimum_fold_count,
                        "support_threshold": float(design.support_min_events_per_fold),
                        "support_ratio": (
                            minimum_fold_count / float(design.support_min_events_per_fold)
                            if design.support_min_events_per_fold > 0
                            else np.nan
                        ),
                        "support_margin": minimum_fold_count - float(design.support_min_events_per_fold),
                        "is_supported_action": bool(common_supported[action_idx]),
                    }
                )
            support_rows.append(
                {
                    "calendar_day": day,
                    "user_group_id": group_id,
                    "audit_unit_id": audit_unit_id,
                    "supported_action_count": len(supported_indices),
                    "action_coverage": action_coverage,
                    "pair_coverage": pair_coverage,
                    "is_valid_audit_unit": valid_unit,
                }
            )
            if not valid_unit:
                continue
            # Cell table uses both folds for the score layer.
            combined_sum = source_sum[d, group_id].sum(axis=0)
            combined_count = source_count[d, group_id].sum(axis=0)
            combined_observed = combined_sum / combined_count
            for route_id, route_array in route_score_arrays.items():
                combined_score = route_array[d, group_id].mean(axis=0)
                for action_idx in supported_indices:
                    cell_rows.append(
                        {
                            "calendar_day": day,
                            "user_group_id": group_id,
                            "audit_unit_id": audit_unit_id,
                            "action_id": arrays.candidate_actions[action_idx],
                            "route_id": route_id,
                            "route_score": float(combined_score[action_idx]),
                            "heldout_target_value": float(combined_observed[action_idx]),
                            "combined_target_count": float(combined_count[action_idx]),
                        }
                    )

            for selection_fold, evaluation_fold in ((0, 1), (1, 0)):
                selection_values = observed_mean[d, group_id, selection_fold]
                evaluation_values = observed_mean[d, group_id, evaluation_fold]
                reference_action = deterministic_tie_argmax(selection_values, supported_indices)
                reference_value = float(evaluation_values[reference_action])
                phi = reference_value - evaluation_values[supported_indices]
                for route_id, route_array in route_score_arrays.items():
                    route_values = route_array[d, group_id, evaluation_fold]
                    route_action = deterministic_tie_argmax(route_values, supported_indices)
                    route_gap = route_values[reference_action] - route_values[supported_indices]
                    gap_errors = np.abs(route_gap - phi)
                    non_reference = supported_indices != reference_action
                    non_tie = non_reference & (np.abs(phi) >= design.near_tie_threshold)
                    sign_agreement = (
                        float(np.mean(np.sign(route_gap[non_tie]) == np.sign(phi[non_tie])))
                        if non_tie.any()
                        else np.nan
                    )
                    unit_rows.append(
                        {
                            "calendar_day": day,
                            "user_group_id": group_id,
                            "audit_unit_id": audit_unit_id,
                            "selection_fold_id": selection_fold,
                            "evaluation_fold_id": evaluation_fold,
                            "route_id": route_id,
                            "reference_action_id": arrays.candidate_actions[reference_action],
                            "route_selected_action_id": arrays.candidate_actions[route_action],
                            "heldout_gap_defect": float(np.max(gap_errors[non_reference])) if non_reference.any() else np.nan,
                            "gap_sign_agreement": sign_agreement,
                            "gap_reversal_rate": 1.0 - sign_agreement if np.isfinite(sign_agreement) else np.nan,
                            "valid_gap_pair_count": int(non_reference.sum()),
                            "near_tie_pair_count": int((non_reference & ~non_tie).sum()),
                            "cross_fitted_ranking_shortfall": reference_value - float(evaluation_values[route_action]),
                            "top_action_match": float(route_action == reference_action),
                        }
                    )

    support_table = pd.DataFrame(support_rows)
    support_margin_table = pd.DataFrame(support_margin_rows)
    unit_table = pd.DataFrame(unit_rows)
    cell_table = pd.DataFrame(cell_rows)
    if cell_table.empty or unit_table.empty:
        raise RuntimeError("Evaluation support is insufficient to construct Exp3 metrics.")

    route_rows: list[dict[str, Any]] = []
    for route_id in cfg.primary_route_ids:
        cells = cell_table[cell_table["route_id"] == route_id]
        units = unit_table[unit_table["route_id"] == route_id]
        # Average the two directions within each audit unit, then average units.
        unit_averages = units.groupby("audit_unit_id", observed=True).agg(
            heldout_gap_defect=("heldout_gap_defect", "mean"),
            gap_sign_agreement=("gap_sign_agreement", "mean"),
            gap_reversal_rate=("gap_reversal_rate", "mean"),
            cross_fitted_ranking_shortfall=("cross_fitted_ranking_shortfall", "mean"),
            top_action_match_rate=("top_action_match", "mean"),
            valid_gap_pair_count=("valid_gap_pair_count", "sum"),
            near_tie_pair_count=("near_tie_pair_count", "sum"),
        )
        meta = ROUTE_META[route_id]
        route_rows.append(
            {
                "route_id": route_id,
                **meta,
                "score_spearman_correlation": spearman_correlation(
                    cells["route_score"].to_numpy(float),
                    cells["heldout_target_value"].to_numpy(float),
                ),
                "score_calibration_mae": float(
                    np.mean(np.abs(cells["route_score"] - cells["heldout_target_value"]))
                ),
                "heldout_gap_defect": float(unit_averages["heldout_gap_defect"].mean()),
                "gap_sign_agreement": float(unit_averages["gap_sign_agreement"].mean()),
                "gap_reversal_rate": float(unit_averages["gap_reversal_rate"].mean()),
                "cross_fitted_ranking_shortfall": float(unit_averages["cross_fitted_ranking_shortfall"].mean()),
                "top_action_match_rate": float(unit_averages["top_action_match_rate"].mean()),
                "valid_gap_pair_count": int(unit_averages["valid_gap_pair_count"].sum()),
                "near_tie_pair_count": int(unit_averages["near_tie_pair_count"].sum()),
                "valid_audit_unit_count": int(len(unit_averages)),
            }
        )
    route_metrics = pd.DataFrame(route_rows)
    support_summary = pd.DataFrame([summarize_support_table(support_table)])

    if decile_membership is None:
        decile_membership = _assign_deciles(cell_table)
    decile_rows: list[dict[str, Any]] = []
    for route_id in ("history_mean_control", "ridge_proxy"):
        cells = cell_table[cell_table["route_id"] == route_id].copy()
        cells["calibration_decile"] = [
            decile_membership.get((route_id, str(row.calendar_day), int(row.user_group_id), str(row.action_id)), np.nan)
            for row in cells.itertuples()
        ]
        cells = cells[cells["calibration_decile"].notna()]
        for decile, group in cells.groupby("calibration_decile", sort=True):
            decile_rows.append(
                {
                    "route_id": route_id,
                    "calibration_decile": int(decile),
                    "mean_predicted_target": float(group["route_score"].mean()),
                    "mean_observed_target": float(group["heldout_target_value"].mean()),
                    "valid_action_cell_count": int(len(group)),
                }
            )
    return MetricResult(
        route_metrics=route_metrics,
        support_metrics=support_summary,
        support_cells=support_table,
        support_margins=support_margin_table,
        audit_unit_metrics=unit_table,
        action_cell_metrics=cell_table,
        decile_calibration=pd.DataFrame(decile_rows),
    )



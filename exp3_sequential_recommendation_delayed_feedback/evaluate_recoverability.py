"""Orchestration for Exp3 score, reference-pair gap, and ranking recovery."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from audit_design import AuditDesign
from config import DEFAULT_CONFIG, ExperimentConfig
from design_contract import ROUTE_SPECS
from evaluation_aggregation import aggregate_user_arrays
from evaluation_artifacts import EvaluationArrays, MetricResult
from evaluation_summary import summarize_route_metrics
from gap_metrics import direction_gap_metrics
from ranking_metrics import direction_ranking_metrics
from score_metrics import assign_deciles, decile_calibration_table
from support_metrics import summarize_support_table, support_record
from utilities import deterministic_tie_argmax


ROUTE_META = {
    route_id: {
        "route_display_name": spec.route_display_name,
        "route_role": spec.route_role,
        "uses_predecision_available_information": spec.uses_predecision_available_information,
        "deployment_value_estimated": spec.deployment_value_estimated,
        "uses_future_outcome": spec.uses_future_outcome,
        "uses_source_identity": spec.uses_source_identity,
    }
    for route_id, spec in ROUTE_SPECS.items()
}


def _route_score_arrays(
    arrays: EvaluationArrays,
    arrival_scores: np.ndarray,
    fold_count: int,
) -> dict[str, np.ndarray]:
    return {
        "arrival_carrier": arrival_scores,
        "history_mean_control": np.repeat(
            arrays.fixed_route_scores["history_mean_control"][:, :, None, :],
            fold_count,
            axis=2,
        ),
        "ridge_proxy": np.repeat(
            arrays.fixed_route_scores["ridge_proxy"][:, :, None, :],
            fold_count,
            axis=2,
        ),
    }


def _cell_rows(
    day: str,
    group_id: int,
    audit_unit_id: str,
    supported_indices: np.ndarray,
    candidate_actions: tuple[str, ...],
    combined_observed: np.ndarray,
    combined_count: np.ndarray,
    route_arrays: dict[str, np.ndarray],
    day_index: int,
) -> list[dict[str, object]]:
    rows = []
    for route_id, route_array in route_arrays.items():
        combined_score = route_array[day_index, group_id].mean(axis=0)
        for action_idx in supported_indices:
            rows.append(
                {
                    "calendar_day": day,
                    "user_group_id": group_id,
                    "audit_unit_id": audit_unit_id,
                    "action_id": candidate_actions[action_idx],
                    "route_id": route_id,
                    "route_score": float(combined_score[action_idx]),
                    "heldout_target_value": float(combined_observed[action_idx]),
                    "combined_target_count": float(combined_count[action_idx]),
                }
            )
    return rows


def compute_metrics(
    arrays: EvaluationArrays,
    design: AuditDesign,
    user_weights: np.ndarray | None = None,
    decile_membership: dict[tuple[str, str, int, str], int] | None = None,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> MetricResult:
    weights = np.ones(len(arrays.user_ids), dtype=float) if user_weights is None else np.asarray(user_weights, dtype=float)
    if weights.shape != (len(arrays.user_ids),):
        raise ValueError("user_weights has the wrong shape")
    source_sum, source_count, arrival_sum, arrival_count = aggregate_user_arrays(
        arrays, weights, design.user_group_count, cfg.reference_fold_count
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        observed_mean = source_sum / source_count
    arrival_scores = np.empty_like(arrival_sum)
    for group_id in range(design.user_group_count):
        prior = arrays.history_scores[group_id]
        arrival_scores[:, group_id] = (
            arrival_sum[:, group_id] + cfg.history_prior_count * prior[None, None, :]
        ) / (arrival_count[:, group_id] + cfg.history_prior_count)
    route_arrays = _route_score_arrays(arrays, arrival_scores, cfg.reference_fold_count)

    unit_rows: list[dict[str, Any]] = []
    cell_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    margin_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    for day_index, day in enumerate(arrays.calendar_days):
        for group_id in range(design.user_group_count):
            supported, support, margins = support_record(
                source_count[day_index, group_id],
                design.support_min_events_per_fold,
                day,
                group_id,
                arrays.candidate_actions,
            )
            support_rows.append(support)
            margin_rows.extend(margins)
            if not support["is_valid_audit_unit"]:
                continue
            combined_sum = source_sum[day_index, group_id].sum(axis=0)
            combined_count = source_count[day_index, group_id].sum(axis=0)
            cell_rows.extend(
                _cell_rows(
                    day,
                    group_id,
                    str(support["audit_unit_id"]),
                    supported,
                    arrays.candidate_actions,
                    combined_sum / combined_count,
                    combined_count,
                    route_arrays,
                    day_index,
                )
            )
            for selection_fold, evaluation_fold in ((0, 1), (1, 0)):
                selection_values = observed_mean[day_index, group_id, selection_fold]
                evaluation_values = observed_mean[day_index, group_id, evaluation_fold]
                reference_action = deterministic_tie_argmax(selection_values, supported)
                heldout_gap = evaluation_values[reference_action] - evaluation_values[supported]
                reference_value = float(evaluation_values[reference_action])
                for route_id, route_array in route_arrays.items():
                    route_selection_values = route_array[day_index, group_id, selection_fold]
                    route_action = deterministic_tie_argmax(route_selection_values, supported)
                    route_gap = (
                        route_selection_values[reference_action]
                        - route_selection_values[supported]
                    )
                    gap, errors, target_gaps, route_gaps = direction_gap_metrics(
                        route_gap,
                        heldout_gap,
                        supported,
                        reference_action,
                        design.near_tie_threshold,
                    )
                    ranking = direction_ranking_metrics(
                        reference_value,
                        float(evaluation_values[route_action]),
                        route_action,
                        reference_action,
                    )
                    base = {
                        "calendar_day": day,
                        "user_group_id": group_id,
                        "audit_unit_id": support["audit_unit_id"],
                        "selection_fold_id": selection_fold,
                        "evaluation_fold_id": evaluation_fold,
                        "route_id": route_id,
                        "reference_action_id": arrays.candidate_actions[reference_action],
                        "route_selected_action_id": arrays.candidate_actions[route_action],
                    }
                    unit_rows.append({**base, **gap, **ranking})
                    alternatives = supported[supported != reference_action]
                    for action_idx, error, target_gap, predicted_gap in zip(
                        alternatives, errors, target_gaps, route_gaps
                    ):
                        pair_rows.append(
                            {
                                **base,
                                "alternative_action_id": arrays.candidate_actions[action_idx],
                                "route_reference_pair_gap": float(predicted_gap),
                                "heldout_reference_pair_gap": float(target_gap),
                                "absolute_reference_pair_gap_error": float(error),
                                "is_near_tie": bool(abs(target_gap) < design.near_tie_threshold),
                            }
                        )

    support_table = pd.DataFrame(support_rows)
    unit_table = pd.DataFrame(unit_rows)
    cell_table = pd.DataFrame(cell_rows)
    if cell_table.empty or unit_table.empty:
        raise RuntimeError("Evaluation support is insufficient to construct Exp3 metrics.")
    route_metrics = summarize_route_metrics(unit_table, cell_table, cfg)
    support_summary = pd.DataFrame([summarize_support_table(support_table)])
    membership = decile_membership or assign_deciles(cell_table)
    return MetricResult(
        route_metrics=route_metrics,
        support_metrics=support_summary,
        support_cells=support_table,
        support_margins=pd.DataFrame(margin_rows),
        audit_unit_metrics=unit_table,
        action_cell_metrics=cell_table,
        decile_calibration=decile_calibration_table(cell_table, membership),
        gap_error_distribution=pd.DataFrame(pair_rows),
    )


_aggregate_user_arrays = aggregate_user_arrays
_assign_deciles = assign_deciles

"""Module C orchestration for calibration-family controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from exp4.calibration.controls import construct_control_signals
from exp4.calibration.evaluation import evaluate_cross_fitted_calibration
from exp4.calibration.temporal_folds import construct_contiguous_temporal_folds
from exp4.configuration.parameters import CALIBRATION
from exp4.configuration.registries import CONTROL_ORDER, CONTROL_REGISTRY
from exp4.metrics.action_gaps import compute_action_gaps
from exp4.routes.source_bound import RouteMapResult
from exp4.simulation.trajectory import StructuralTrajectory


@dataclass(frozen=True)
class ModuleCResult:
    replication_records: list[dict[str, Any]]
    parameter_records: list[dict[str, Any]]
    correspondence_records: list[dict[str, Any]]


def _rank_columns(values: np.ndarray) -> np.ndarray:
    ranks = np.empty_like(values, dtype=np.float64)
    for column in range(values.shape[1]):
        ranks[:, column] = np.argsort(
            np.argsort(values[:, column], kind="stable"), kind="stable"
        )
    return ranks


def _mean_abs_spearman(first: np.ndarray, second: np.ndarray) -> float:
    first_rank = _rank_columns(first)
    second_rank = _rank_columns(second)
    correlations: list[float] = []
    for column in range(first.shape[1]):
        if float(np.std(first_rank[:, column])) <= 1e-14:
            continue
        correlations.append(
            abs(float(np.corrcoef(first_rank[:, column], second_rank[:, column])[0, 1]))
        )
    return float(np.mean(correlations)) if correlations else np.nan


def run_module_c(
    replication_id: int,
    trajectory: StructuralTrajectory,
    proxy_route: RouteMapResult,
) -> ModuleCResult:
    evaluation = trajectory.evaluation_slice
    base_route_gaps = compute_action_gaps(proxy_route.route_loss_map[evaluation])
    base_structural_gaps = compute_action_gaps(
        trajectory.structural_loss_map[evaluation]
    )
    fold_ids = construct_contiguous_temporal_folds(
        len(base_route_gaps), CALIBRATION.temporal_folds
    )
    inclusion_mask = (
        trajectory.calibration_label_uniforms[evaluation]
        < CALIBRATION.audit_evidence_rate
    )
    weights = np.ones(len(base_route_gaps), dtype=np.float64)
    replication_records: list[dict[str, Any]] = []
    parameter_records: list[dict[str, Any]] = []
    correspondence_records: list[dict[str, Any]] = []
    for control_id in CONTROL_ORDER:
        signals = construct_control_signals(
            control_id,
            base_route_gaps,
            base_structural_gaps,
            fold_ids,
            replication_id,
        )
        evaluation_result = evaluate_cross_fitted_calibration(
            control_id,
            signals.route_gaps,
            signals.structural_gaps,
            fold_ids,
            inclusion_mask,
            weights,
            replication_id,
            signals.true_intercept,
            signals.true_slope,
        )
        parameter_records.extend(evaluation_result.parameter_records)
        replication_records.append(
            {
                "replication_id": int(replication_id),
                "control_id": control_id,
                "control_display_name": CONTROL_REGISTRY[control_id]["display_name"],
                "analysis_tier": CONTROL_REGISTRY[control_id]["analysis_tier"],
                "correspondence_status": CONTROL_REGISTRY[control_id]["correspondence"],
                "raw_defect": evaluation_result.raw_defect,
                "oof_calibrated_defect": evaluation_result.calibrated_defect,
                "recoverability": evaluation_result.recoverability,
                "negative_recoverability_indicator": (
                    bool(evaluation_result.recoverability < 0.0)
                    if np.isfinite(evaluation_result.recoverability)
                    else False
                ),
                "estimable": evaluation_result.estimable,
                "status": evaluation_result.status,
                "minimum_training_support": evaluation_result.minimum_training_support,
                "labelled_sample_size": int(np.sum(inclusion_mask)),
                "calibration_audit_evidence_rate": CALIBRATION.audit_evidence_rate,
            }
        )
        correspondence_records.append(
            {
                "replication_id": int(replication_id),
                "control_id": control_id,
                "pre_mean_abs_pearson": signals.pre_mean_abs_pearson,
                "post_mean_abs_pearson": signals.post_mean_abs_pearson,
                "pre_mean_abs_spearman": _mean_abs_spearman(
                    base_route_gaps, signals.structural_gaps
                ),
                "post_mean_abs_spearman": _mean_abs_spearman(
                    signals.route_gaps, signals.structural_gaps
                ),
                "mean_difference_in_pair_marginal_mean": signals.marginal_mean_difference,
                "mean_difference_in_pair_marginal_sd": signals.marginal_sd_difference,
                "permutation_hash": signals.permutation_hash,
            }
        )
    return ModuleCResult(
        replication_records, parameter_records, correspondence_records
    )

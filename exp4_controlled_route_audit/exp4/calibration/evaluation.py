"""Out-of-fold pair-specific affine calibration evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from exp4.calibration.affine import (
    fit_weighted_affine_calibration,
    predict_affine_calibration,
)
from exp4.configuration.parameters import CALIBRATION, REPORTING
from exp4.metrics.action_gaps import action_pair_indices


@dataclass(frozen=True)
class CalibrationEvaluation:
    raw_pairwise_discrepancy: float
    oof_calibrated_pairwise_discrepancy: float
    recoverability: float
    estimable: bool
    status: str
    minimum_training_support: int
    parameter_records: list[dict[str, Any]]


def evaluate_cross_fitted_calibration(
    control_id: str,
    route_gaps: np.ndarray,
    structural_gaps: np.ndarray,
    fold_ids: np.ndarray,
    inclusion_mask: np.ndarray,
    weights: np.ndarray,
    replication_id: int,
    true_intercept: float | None,
    true_slope: float | None,
) -> CalibrationEvaluation:
    pair_low, pair_high = action_pair_indices(10)
    predictions = np.full_like(route_gaps, np.nan, dtype=np.float64)
    parameter_records: list[dict[str, Any]] = []
    all_estimable = True
    minimum_support = len(route_gaps)
    for fold_id in range(CALIBRATION.temporal_folds):
        held_out = fold_ids == fold_id
        training = inclusion_mask & ~held_out
        training_positions = np.flatnonzero(training)
        for pair_index, (action_low, action_high) in enumerate(
            zip(pair_low, pair_high, strict=True)
        ):
            fit = fit_weighted_affine_calibration(
                route_gaps[training_positions, pair_index],
                structural_gaps[training_positions, pair_index],
                weights[training_positions],
            )
            minimum_support = min(minimum_support, fit.training_support)
            all_estimable = all_estimable and fit.estimable
            if fit.estimable:
                predictions[held_out, pair_index] = predict_affine_calibration(
                    route_gaps[held_out, pair_index], fit
                )
            parameter_records.append(
                {
                    "replication_id": int(replication_id),
                    "control_id": control_id,
                    "fold_id": int(fold_id),
                    "action_pair_low": int(action_low),
                    "action_pair_high": int(action_high),
                    "intercept": fit.intercept,
                    "slope": fit.slope,
                    "training_support": fit.training_support,
                    "weighted_support": fit.weighted_support,
                    "route_gap_variance": fit.route_gap_variance,
                    "estimable": fit.estimable,
                    "status": fit.status,
                    "true_intercept": true_intercept,
                    "true_slope": true_slope,
                    "held_out_fold_excluded_from_training": True,
                }
            )
    labelled = np.asarray(inclusion_mask, dtype=bool)
    labelled_weights = np.asarray(weights, dtype=np.float64)[labelled]
    # v3 aggregation: unit discrepancy is the PAIR AVERAGE of absolute
    # route-vs-structural gap errors, not the round-max defect.
    raw_unit = np.mean(np.abs(route_gaps - structural_gaps), axis=1)
    raw_pairwise = float(
        np.sum(labelled_weights * raw_unit[labelled]) / np.sum(labelled_weights)
    )
    if not all_estimable:
        return CalibrationEvaluation(
            raw_pairwise,
            np.nan,
            np.nan,
            False,
            "NOT_ESTIMABLE",
            minimum_support,
            parameter_records,
        )
    calibrated_unit = np.mean(np.abs(predictions - structural_gaps), axis=1)
    calibrated_pairwise = float(
        np.sum(labelled_weights * calibrated_unit[labelled]) / np.sum(labelled_weights)
    )
    recoverability = (
        1.0 - calibrated_pairwise / raw_pairwise
        if raw_pairwise > REPORTING.raw_pairwise_discrepancy_epsilon
        else np.nan
    )
    return CalibrationEvaluation(
        raw_pairwise,
        calibrated_pairwise,
        float(recoverability),
        True,
        "ESTIMABLE",
        minimum_support,
        parameter_records,
    )

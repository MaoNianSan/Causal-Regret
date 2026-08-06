"""Prespecified correspondence-preserved and correspondence-destroyed controls."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

import numpy as np

from exp4.configuration.parameters import CALIBRATION
from exp4.simulation.trajectory import generator_for


@dataclass(frozen=True)
class CalibrationControlSignals:
    control_id: str
    route_gaps: np.ndarray
    structural_gaps: np.ndarray
    true_intercept: float | None
    true_slope: float | None
    permutation_hash: str | None
    pre_mean_abs_pearson: float
    post_mean_abs_pearson: float
    marginal_mean_difference: float
    marginal_sd_difference: float


def _mean_abs_pair_correlation(first: np.ndarray, second: np.ndarray) -> float:
    correlations: list[float] = []
    for pair_index in range(first.shape[1]):
        x = first[:, pair_index]
        y = second[:, pair_index]
        if float(np.std(x)) <= 1e-14 or float(np.std(y)) <= 1e-14:
            continue
        correlations.append(abs(float(np.corrcoef(x, y)[0, 1])))
    return float(np.mean(correlations)) if correlations else np.nan


def construct_control_signals(
    control_id: str,
    base_route_gaps: np.ndarray,
    base_structural_gaps: np.ndarray,
    fold_ids: np.ndarray,
    replication_id: int,
) -> CalibrationControlSignals:
    if control_id == "affine_linked":
        rng = generator_for("module_c_affine", replication_id, "control_noise")
        linked = CALIBRATION.affine_intercept + CALIBRATION.affine_slope * base_route_gaps
        pair_scale = np.std(linked, axis=0, ddof=1)
        noise = rng.normal(size=linked.shape) * (CALIBRATION.affine_noise_fraction * pair_scale)[None, :]
        structural = linked + noise
        correlation = _mean_abs_pair_correlation(base_route_gaps, structural)
        return CalibrationControlSignals(
            control_id,
            base_route_gaps.copy(),
            structural,
            CALIBRATION.affine_intercept,
            CALIBRATION.affine_slope,
            None,
            correlation,
            correlation,
            0.0,
            0.0,
        )
    if control_id == "blocked_correspondence_destroyed":
        rng = generator_for("module_c_blocked", replication_id, "control_permutation")
        shuffled = base_route_gaps.copy()
        digest = hashlib.sha256()
        mean_differences: list[float] = []
        sd_differences: list[float] = []
        for fold_id in np.unique(fold_ids):
            positions = np.flatnonzero(fold_ids == fold_id)
            for pair_index in range(shuffled.shape[1]):
                permutation = rng.permutation(positions)
                digest.update(np.ascontiguousarray(permutation).tobytes())
                original = base_route_gaps[positions, pair_index]
                permuted = base_route_gaps[permutation, pair_index]
                shuffled[positions, pair_index] = permuted
                mean_differences.append(abs(float(np.mean(original) - np.mean(permuted))))
                sd_differences.append(abs(float(np.std(original) - np.std(permuted))))
        return CalibrationControlSignals(
            control_id,
            shuffled,
            base_structural_gaps.copy(),
            None,
            None,
            digest.hexdigest(),
            _mean_abs_pair_correlation(base_route_gaps, base_structural_gaps),
            _mean_abs_pair_correlation(shuffled, base_structural_gaps),
            float(np.mean(mean_differences)),
            float(np.mean(sd_differences)),
        )
    if control_id == "nonlinear_monotone":
        rng = generator_for("module_c_nonlinear", replication_id, "control_noise")
        transformed = np.tanh(CALIBRATION.nonlinear_scale * base_route_gaps)
        pair_scale = np.std(transformed, axis=0, ddof=1)
        structural = transformed + rng.normal(size=transformed.shape) * (
            CALIBRATION.affine_noise_fraction * pair_scale
        )[None, :]
        correlation = _mean_abs_pair_correlation(base_route_gaps, structural)
        return CalibrationControlSignals(
            control_id,
            base_route_gaps.copy(),
            structural,
            None,
            None,
            None,
            correlation,
            correlation,
            0.0,
            0.0,
        )
    raise KeyError(f"Unknown control_id: {control_id}")

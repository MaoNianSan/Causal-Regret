"""Empirical user-cluster resampling ranges and bias diagnostics for Exp3.

The displayed range is the empirical percentile range of complete user-cluster
resampling reconstructions. It is a sensitivity diagnostic, not a formally
validated confidence interval. Basic-bootstrap reflections are retained only in
the audit table so earlier results remain explainable.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MetricBounds:
    lower: float | None = None
    upper: float | None = None


CANONICAL_ROUTE_METRIC_BOUNDS: dict[str, MetricBounds] = {
    "pooled_supported_cell_spearman": MetricBounds(-1.0, 1.0),
    "pooled_supported_cell_mae": MetricBounds(0.0, None),
    "exposure_weighted_supported_cell_mae": MetricBounds(0.0, None),
    "within_audit_unit_centered_spearman": MetricBounds(-1.0, 1.0),
    "calibration_intercept": MetricBounds(None, None),
    "calibration_slope": MetricBounds(None, None),
    "maximum_heldout_reference_pair_gap_error": MetricBounds(0.0, None),
    "mean_absolute_reference_pair_gap_error": MetricBounds(0.0, None),
    "p90_absolute_reference_pair_gap_error": MetricBounds(0.0, None),
    "heldout_reference_pair_sign_agreement": MetricBounds(0.0, 1.0),
    "near_tie_pair_share": MetricBounds(0.0, 1.0),
    "signed_cross_fitted_reference_minus_route_value_difference": MetricBounds(None, None),
    "top_action_agreement_with_fold_reference": MetricBounds(0.0, 1.0),
}

ROUTE_METRIC_BOUNDS: dict[str, MetricBounds] = {
    "score_spearman_correlation": MetricBounds(-1.0, 1.0),
    "score_calibration_mae": MetricBounds(0.0, None),
    "heldout_gap_defect": MetricBounds(0.0, None),
    "gap_sign_agreement": MetricBounds(0.0, 1.0),
    "gap_reversal_rate": MetricBounds(0.0, 1.0),
    "cross_fitted_ranking_shortfall": MetricBounds(None, None),
    "top_action_match_rate": MetricBounds(0.0, 1.0),
}


def metric_bounds(metric_id: str) -> MetricBounds:
    if metric_id in CANONICAL_ROUTE_METRIC_BOUNDS:
        return CANONICAL_ROUTE_METRIC_BOUNDS[metric_id]
    return ROUTE_METRIC_BOUNDS[metric_id]


def _finite(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    return array[np.isfinite(array)]


def _clip(value: float, bounds: MetricBounds) -> float:
    if bounds.lower is not None:
        value = max(float(bounds.lower), value)
    if bounds.upper is not None:
        value = min(float(bounds.upper), value)
    return float(value)


def percentile_range(values: np.ndarray, level: float) -> tuple[float, float]:
    finite = _finite(values)
    if finite.size == 0:
        return np.nan, np.nan
    alpha = 1.0 - float(level)
    return (
        float(np.quantile(finite, alpha / 2.0)),
        float(np.quantile(finite, 1.0 - alpha / 2.0)),
    )


def basic_interval_audit(
    point_estimate: float,
    values: np.ndarray,
    level: float,
    bounds: MetricBounds = MetricBounds(),
) -> tuple[float, float]:
    """Return the legacy basic-bootstrap reflection for audit only."""
    percentile_low, percentile_high = percentile_range(values, level)
    if not np.isfinite(percentile_low) or not np.isfinite(percentile_high):
        return np.nan, np.nan
    lower = _clip(2.0 * float(point_estimate) - percentile_high, bounds)
    upper = _clip(2.0 * float(point_estimate) - percentile_low, bounds)
    return (float(min(lower, upper)), float(max(lower, upper)))


def resampling_audit(
    *,
    metric_id: str,
    point_estimate: float,
    values: np.ndarray,
    range_level: float,
    bounds: MetricBounds = MetricBounds(),
) -> dict[str, object]:
    finite = _finite(values)
    sensitivity_low, sensitivity_high = percentile_range(finite, range_level)
    basic_low, basic_high = basic_interval_audit(point_estimate, finite, range_level, bounds)
    mean = float(np.mean(finite)) if finite.size else np.nan
    median = float(np.median(finite)) if finite.size else np.nan
    sd = float(np.std(finite, ddof=1)) if finite.size > 1 else np.nan
    bias = mean - float(point_estimate) if np.isfinite(mean) else np.nan
    bias_over_sd = bias / sd if np.isfinite(sd) and sd > 0 else np.nan
    return {
        "metric_id": metric_id,
        "point_estimate": float(point_estimate),
        "finite_resampling_count": int(finite.size),
        "resampling_mean": mean,
        "resampling_median": median,
        "resampling_sd": sd,
        "resampling_bias": bias,
        "absolute_bias_over_sd": abs(float(bias_over_sd)) if np.isfinite(bias_over_sd) else np.nan,
        "sensitivity_range_level": float(range_level),
        "sensitivity_range_method": "percentile_user_cluster_sensitivity",
        "sensitivity_lower": sensitivity_low,
        "sensitivity_upper": sensitivity_high,
        "point_inside_sensitivity_range": bool(
            np.isfinite(sensitivity_low)
            and np.isfinite(sensitivity_high)
            and sensitivity_low <= float(point_estimate) <= sensitivity_high
        ),
        "formal_ci_validated": False,
        "legacy_basic_lower_audit_only": basic_low,
        "legacy_basic_upper_audit_only": basic_high,
        "point_inside_legacy_basic_audit": bool(
            np.isfinite(basic_low)
            and np.isfinite(basic_high)
            and basic_low <= float(point_estimate) <= basic_high
        ),
        "parameter_lower_bound": bounds.lower,
        "parameter_upper_bound": bounds.upper,
    }


# Backward-compatible function name for internal callers. Its output contract is
# now explicitly sensitivity-oriented.
def interval_audit(
    *,
    metric_id: str,
    point_estimate: float,
    values: np.ndarray,
    range_level: float | None = None,
    ci_level: float | None = None,
    bounds: MetricBounds = MetricBounds(),
) -> dict[str, object]:
    level = range_level if range_level is not None else ci_level
    if level is None:
        raise ValueError("A resampling range level is required")
    return resampling_audit(
        metric_id=metric_id,
        point_estimate=point_estimate,
        values=values,
        range_level=float(level),
        bounds=bounds,
    )

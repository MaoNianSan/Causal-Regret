"""Pair-specific weighted affine fits with no fallback behavior."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from exp4.configuration.parameters import CALIBRATION


@dataclass(frozen=True)
class AffineFitResult:
    intercept: float
    slope: float
    training_support: int
    weighted_support: float
    route_gap_variance: float
    estimable: bool
    status: str


def fit_weighted_affine_calibration(
    route_gap: np.ndarray,
    structural_gap: np.ndarray,
    weights: np.ndarray,
) -> AffineFitResult:
    x = np.asarray(route_gap, dtype=np.float64)
    y = np.asarray(structural_gap, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    support = len(x)
    if support < CALIBRATION.minimum_training_support:
        return AffineFitResult(np.nan, np.nan, support, float(np.sum(w)), np.nan, False, "INSUFFICIENT_SUPPORT")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        return AffineFitResult(np.nan, np.nan, support, float(np.sum(w)), np.nan, False, "NON_FINITE_SIGNAL")
    if not np.all(np.isfinite(w)) or np.any(w <= 0.0):
        return AffineFitResult(np.nan, np.nan, support, np.nan, np.nan, False, "INVALID_WEIGHTS")
    weighted_support = float(np.sum(w))
    if weighted_support <= 0.0:
        return AffineFitResult(np.nan, np.nan, support, weighted_support, np.nan, False, "ZERO_WEIGHT_SUM")
    x_mean = float(np.sum(w * x) / weighted_support)
    y_mean = float(np.sum(w * y) / weighted_support)
    centered_x = x - x_mean
    variance = float(np.sum(w * centered_x**2) / weighted_support)
    if variance <= CALIBRATION.variance_tolerance:
        return AffineFitResult(np.nan, np.nan, support, weighted_support, variance, False, "ZERO_ROUTE_GAP_VARIANCE")
    covariance = float(np.sum(w * centered_x * (y - y_mean)) / weighted_support)
    slope = covariance / variance
    intercept = y_mean - slope * x_mean
    if not np.isfinite(slope) or not np.isfinite(intercept):
        return AffineFitResult(np.nan, np.nan, support, weighted_support, variance, False, "NON_FINITE_PARAMETERS")
    return AffineFitResult(intercept, slope, support, weighted_support, variance, True, "ESTIMABLE")


def predict_affine_calibration(route_gap: np.ndarray, fit: AffineFitResult) -> np.ndarray:
    if not fit.estimable:
        raise ValueError("Cannot predict from a non-estimable affine fit")
    return fit.intercept + fit.slope * np.asarray(route_gap, dtype=np.float64)

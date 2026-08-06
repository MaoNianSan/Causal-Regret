"""Pure audit estimators with explicit non-estimability."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


class NotEstimableError(RuntimeError):
    pass


@dataclass(frozen=True)
class EstimateResult:
    estimate: float
    status: str
    sample_size: int


def _validate(values: np.ndarray, weights: np.ndarray) -> None:
    if len(values) == 0:
        raise NotEstimableError("EMPTY_SAMPLE")
    if not np.all(np.isfinite(values)):
        raise NotEstimableError("NON_FINITE_VALUES")
    if not np.all(np.isfinite(weights)) or np.any(weights <= 0.0):
        raise NotEstimableError("INVALID_WEIGHTS")
    if float(np.sum(weights)) <= 0.0:
        raise NotEstimableError("ZERO_DENOMINATOR")


def estimate_unweighted_mean(values: np.ndarray) -> EstimateResult:
    values = np.asarray(values, dtype=np.float64)
    weights = np.ones(len(values), dtype=np.float64)
    _validate(values, weights)
    return EstimateResult(float(np.mean(values)), "ESTIMABLE", len(values))


def estimate_hajek_ipw_mean(values: np.ndarray, weights: np.ndarray) -> EstimateResult:
    values = np.asarray(values, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    _validate(values, weights)
    estimate = float(np.sum(weights * values) / np.sum(weights))
    return EstimateResult(estimate, "ESTIMABLE", len(values))

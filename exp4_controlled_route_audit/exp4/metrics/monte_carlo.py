"""Monte Carlo precision utilities."""

from __future__ import annotations

import numpy as np


def mean_mcse(values: np.ndarray) -> float:
    finite = np.asarray(values, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if finite.size <= 1:
        return 0.0
    return float(np.std(finite, ddof=1) / np.sqrt(finite.size))


def rmse_mcse(errors: np.ndarray) -> tuple[float, str]:
    finite = np.asarray(errors, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if finite.size <= 1:
        return 0.0, "degenerate"
    squared = finite**2
    m2 = float(np.mean(squared))
    if m2 <= 1e-20:
        return 0.0, "exact_zero"
    value = float(np.std(squared, ddof=1) / (2.0 * np.sqrt(finite.size) * np.sqrt(m2)))
    return value, "squared_error_delta"


def percentile_interval(values: np.ndarray, confidence_level: float) -> tuple[float, float]:
    alpha = (1.0 - float(confidence_level)) / 2.0
    return float(np.quantile(values, alpha)), float(np.quantile(values, 1.0 - alpha))

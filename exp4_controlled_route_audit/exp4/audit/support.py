"""Effective support and weight-distribution diagnostics."""

from __future__ import annotations

import numpy as np


def compute_effective_sample_size(weights: np.ndarray) -> float:
    values = np.asarray(weights, dtype=np.float64)
    if values.size == 0:
        return np.nan
    if np.any(values <= 0.0) or not np.all(np.isfinite(values)):
        return np.nan
    denominator = float(np.sum(values**2))
    if denominator <= 0.0:
        return np.nan
    return float(np.sum(values) ** 2 / denominator)


def weight_diagnostics(
    included_weights: np.ndarray,
    inclusion_probabilities: np.ndarray,
) -> dict[str, float]:
    weights = np.asarray(included_weights, dtype=np.float64)
    probabilities = np.asarray(inclusion_probabilities, dtype=np.float64)
    if weights.size == 0:
        return {
            key: np.nan
            for key in (
                "weight_min",
                "weight_median",
                "weight_p95",
                "weight_max",
                "weight_cv",
                "lower_clip_fraction",
                "upper_clip_fraction",
            )
        }
    mean_weight = float(np.mean(weights))
    return {
        "weight_min": float(np.min(weights)),
        "weight_median": float(np.median(weights)),
        "weight_p95": float(np.quantile(weights, 0.95)),
        "weight_max": float(np.max(weights)),
        "weight_cv": (
            float(np.std(weights, ddof=1) / mean_weight)
            if len(weights) > 1 and mean_weight > 0.0
            else 0.0
        ),
        "lower_clip_fraction": float(
            np.mean(np.isclose(probabilities, MODULE_B_LOWER, atol=1e-12))
        ),
        "upper_clip_fraction": float(
            np.mean(np.isclose(probabilities, MODULE_B_UPPER, atol=1e-12))
        ),
    }


from exp4.configuration.parameters import MODULE_B

MODULE_B_LOWER = MODULE_B.inclusion_lower_bound
MODULE_B_UPPER = MODULE_B.inclusion_upper_bound

"""Held-out reference-pair gap metrics."""
from __future__ import annotations

import numpy as np


def direction_gap_metrics(
    route_gap: np.ndarray,
    heldout_gap: np.ndarray,
    supported_indices: np.ndarray,
    reference_action: int,
    near_tie_threshold: float,
) -> tuple[dict[str, float | int], np.ndarray, np.ndarray, np.ndarray]:
    non_reference = supported_indices != reference_action
    errors = np.abs(route_gap - heldout_gap)
    valid_errors = errors[non_reference]
    valid_gaps = heldout_gap[non_reference]
    valid_route_gaps = route_gap[non_reference]
    near_tie = np.abs(valid_gaps) < near_tie_threshold
    non_tie = ~near_tie
    sign_agreement = (
        float(np.mean(np.sign(valid_route_gaps[non_tie]) == np.sign(valid_gaps[non_tie])))
        if non_tie.any()
        else np.nan
    )
    valid_count = int(non_reference.sum())
    near_tie_count = int(near_tie.sum())
    maximum = float(np.max(valid_errors)) if valid_count else np.nan
    mean_error = float(np.mean(valid_errors)) if valid_count else np.nan
    p90_error = float(np.quantile(valid_errors, 0.9)) if valid_count else np.nan
    metrics = {
        "maximum_heldout_reference_pair_gap_error": maximum,
        "mean_absolute_reference_pair_gap_error": mean_error,
        "p90_absolute_reference_pair_gap_error": p90_error,
        "heldout_reference_pair_sign_agreement": sign_agreement,
        "valid_reference_pair_count": valid_count,
        "near_tie_pair_count": near_tie_count,
        "near_tie_pair_share": near_tie_count / valid_count if valid_count else np.nan,
        "heldout_gap_defect": maximum,
        "gap_sign_agreement": sign_agreement,
        "gap_reversal_rate": 1.0 - sign_agreement if np.isfinite(sign_agreement) else np.nan,
        "valid_gap_pair_count": valid_count,
    }
    return metrics, valid_errors, valid_gaps, valid_route_gaps

"""Logged-supported ranking metrics and paired contrast helpers."""
from __future__ import annotations

import pandas as pd


def direction_ranking_metrics(
    reference_heldout_value: float,
    route_heldout_value: float,
    route_action: int,
    reference_action: int,
) -> dict[str, float]:
    difference = reference_heldout_value - route_heldout_value
    agreement = float(route_action == reference_action)
    return {
        "signed_cross_fitted_reference_minus_route_value_difference": difference,
        "top_action_agreement_with_fold_reference": agreement,
        "cross_fitted_ranking_shortfall": difference,
        "top_action_match": agreement,
    }


def ridge_over_historical_paired_value_gain(route_metrics: pd.DataFrame) -> float:
    values = route_metrics.set_index("route_id")[
        "signed_cross_fitted_reference_minus_route_value_difference"
    ]
    return float(values["history_mean_control"] - values["ridge_proxy"])

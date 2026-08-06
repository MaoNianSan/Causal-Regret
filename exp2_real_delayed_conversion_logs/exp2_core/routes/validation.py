from __future__ import annotations

import pandas as pd

from contracts import CREDIT_TOLERANCE, ScientificInvariantError


def validate_credit_conservation(assignments: pd.DataFrame) -> pd.DataFrame:
    if assignments.empty:
        raise ScientificInvariantError("No route assignments were constructed.")
    if assignments["credit_weight"].lt(-CREDIT_TOLERANCE).any():
        raise ScientificInvariantError("A route assignment has negative credit weight.")
    totals = (
        assignments.groupby(["route_id", "journey_id"], sort=False, observed=True)["credit_weight"]
        .sum()
        .reset_index(name="credit_weight_sum")
    )
    totals["absolute_error"] = (totals["credit_weight_sum"] - 1.0).abs()
    bad = totals.loc[totals["absolute_error"].gt(CREDIT_TOLERANCE)]
    if not bad.empty:
        example = bad.head(5).to_dict(orient="records")
        raise ScientificInvariantError(f"Credit conservation failed: {example}")
    return (
        totals.groupby("route_id", sort=False)
        .agg(
            assigned_journey_count=("journey_id", "nunique"),
            maximum_credit_sum_error=("absolute_error", "max"),
        )
        .reset_index()
    )

from __future__ import annotations

import numpy as np
import pandas as pd

from contracts import ROUTE_SPECS, ScientificInvariantError


def attach_route_metadata(frame: pd.DataFrame, route_id: str) -> pd.DataFrame:
    spec = ROUTE_SPECS[route_id]
    output = frame.copy()
    output["route_id"] = route_id
    output["analysis_tier"] = spec.analysis_tier
    output["route_role"] = spec.route_role
    output["source_bound"] = spec.source_bound
    output["deployable"] = spec.deployable
    return output


def normalize_group_weights(frame: pd.DataFrame, raw_weight: pd.Series) -> pd.Series:
    weights = pd.to_numeric(raw_weight, errors="coerce").fillna(0.0).clip(lower=0.0)
    totals = weights.groupby(frame["journey_id"], sort=False).transform("sum")
    if totals.le(0).any():
        bad = frame.loc[totals.le(0), "journey_id"].astype(str).unique()[:5]
        raise ScientificInvariantError(f"Nonpositive route-weight totals for journeys: {bad.tolist()}")
    return weights / totals


def aggregate_assignment_rows(
    frame: pd.DataFrame,
    *,
    route_id: str,
    raw_weight: pd.Series,
) -> pd.DataFrame:
    work = frame[["journey_id", "decision_cell_id", "source_lag_days"]].copy()
    work["row_weight"] = pd.to_numeric(raw_weight, errors="coerce").fillna(0.0)
    aggregated = (
        work.groupby(["journey_id", "decision_cell_id"], sort=False, observed=True)
        .agg(
            raw_weight=("row_weight", "sum"),
            weighted_lag_numerator=(
                "source_lag_days",
                lambda values: float(np.nansum(values.to_numpy(dtype=float))),
            ),
            source_row_count=("source_lag_days", "size"),
        )
        .reset_index()
    )
    aggregated["credit_weight"] = normalize_group_weights(aggregated, aggregated["raw_weight"])
    aggregated["source_lag_days"] = (
        aggregated["weighted_lag_numerator"] / aggregated["source_row_count"].clip(lower=1)
    )
    aggregated = aggregated.drop(columns=["raw_weight", "weighted_lag_numerator", "source_row_count"])
    return attach_route_metadata(aggregated, route_id)

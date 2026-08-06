from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from contracts import METRIC_TOLERANCE, PRIMARY_ROUTE_ORDER, ScientificInvariantError


def build_route_allocations(
    assignments: pd.DataFrame,
    decision_cells: pd.DataFrame,
    *,
    route_ids: Iterable[str] = PRIMARY_ROUTE_ORDER,
) -> pd.DataFrame:
    route_ids = tuple(route_ids)
    cells = decision_cells[
        [
            "decision_cell_id",
            "campaign_id",
            "source_date_utc",
            "eligible_impression_count",
        ]
    ].copy()
    routes = pd.DataFrame({"route_id": list(route_ids)})
    routes["_join_key"] = 1
    cells["_join_key"] = 1
    grid = routes.merge(cells, on="_join_key", how="inner").drop(columns="_join_key")

    credits = (
        assignments.loc[assignments["route_id"].isin(route_ids)]
        .groupby(["route_id", "decision_cell_id"], sort=False, observed=True)["credit_weight"]
        .sum()
        .rename("credited_conversion_mass")
        .reset_index()
    )
    output = grid.merge(
        credits,
        on=["route_id", "decision_cell_id"],
        how="left",
        validate="one_to_one",
    )
    output["credited_conversion_mass"] = output["credited_conversion_mass"].fillna(0.0)
    route_totals = output.groupby("route_id", sort=False)["credited_conversion_mass"].transform("sum")
    if route_totals.le(0).any():
        raise ScientificInvariantError("A primary route has nonpositive total credit.")
    output["allocation_share"] = output["credited_conversion_mass"] / route_totals
    output["source_time_credit_score"] = (
        output["credited_conversion_mass"]
        / output["eligible_impression_count"].to_numpy(dtype=float)
    )
    output["positive_credit"] = output["credited_conversion_mass"].gt(0)

    allocation_sums = output.groupby("route_id", sort=False)["allocation_share"].sum()
    if not np.allclose(allocation_sums.to_numpy(), 1.0, atol=METRIC_TOLERANCE, rtol=0.0):
        raise ScientificInvariantError(
            f"Allocation shares do not sum to one: {allocation_sums.to_dict()}"
        )
    return output.sort_values(
        ["route_id", "campaign_id", "source_date_utc", "decision_cell_id"],
        kind="stable",
    ).reset_index(drop=True)


def allocation_tv(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    if left.shape != right.shape:
        raise ScientificInvariantError("Allocation vectors have different shapes.")
    value = 0.5 * float(np.abs(left - right).sum())
    if value < -METRIC_TOLERANCE or value > 1.0 + METRIC_TOLERANCE:
        raise ScientificInvariantError(f"Allocation TV outside [0,1]: {value}")
    return float(np.clip(value, 0.0, 1.0))

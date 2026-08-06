from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

from contracts import PRIMARY_SOURCE_ROUTE_ORDER

from .allocation import build_route_allocations
from .ranking import pair_metrics_from_allocations


def compute_mean_journey_assignment_tv(
    assignments: pd.DataFrame,
    left_route: str,
    right_route: str,
    *,
    journey_ids: set[str] | None = None,
) -> float:
    columns = ["journey_id", "decision_cell_id", "credit_weight"]
    left = assignments.loc[assignments["route_id"].eq(left_route), columns].copy()
    right = assignments.loc[assignments["route_id"].eq(right_route), columns].copy()
    if journey_ids is not None:
        left = left.loc[left["journey_id"].astype(str).isin(journey_ids)]
        right = right.loc[right["journey_id"].astype(str).isin(journey_ids)]
    merged = left.merge(
        right,
        on=["journey_id", "decision_cell_id"],
        how="outer",
        suffixes=("_left", "_right"),
    ).fillna({"credit_weight_left": 0.0, "credit_weight_right": 0.0})
    merged["absolute_difference"] = (
        merged["credit_weight_left"] - merged["credit_weight_right"]
    ).abs()
    journey_tv = (
        0.5
        * merged.groupby("journey_id", sort=False, observed=True)["absolute_difference"].sum()
    )
    return float(journey_tv.mean()) if len(journey_tv) else float("nan")


def _assignment_entropy(frame: pd.DataFrame) -> pd.Series:
    work = frame.copy()
    positive = work["credit_weight"].clip(lower=np.finfo(float).tiny)
    work["entropy_term"] = -work["credit_weight"] * np.log(positive)
    return work.groupby("journey_id", sort=False, observed=True)["entropy_term"].sum()


def compute_ambiguity_strata_metrics(
    assignments: pd.DataFrame,
    decision_cells: pd.DataFrame,
    journey_manifest: pd.DataFrame,
    *,
    top_k: int,
) -> pd.DataFrame:
    retained = journey_manifest.loc[journey_manifest["is_primary_eligible"]].copy()
    records: list[dict[str, object]] = []
    for stratum in ("candidate_cells_1", "candidate_cells_2", "candidate_cells_3plus"):
        journeys = retained.loc[retained["ambiguity_stratum"].eq(stratum)].copy()
        journey_ids = set(journeys["journey_id"].astype(str))
        records.append(
            {
                "record_type": "stratum_summary",
                "ambiguity_stratum": stratum,
                "attribution_degenerate": stratum == "candidate_cells_1",
                "journey_count": int(len(journeys)),
                "user_count": int(journeys["user_id"].nunique()),
                "journey_share": len(journeys) / max(len(retained), 1),
            }
        )
        if not journey_ids:
            continue

        stratum_assignments = assignments.loc[
            assignments["journey_id"].astype(str).isin(journey_ids)
        ].copy()
        for route_id, route_frame in stratum_assignments.groupby(
            "route_id", sort=False, observed=True
        ):
            entropy = _assignment_entropy(route_frame)
            maximum = route_frame.groupby("journey_id", sort=False, observed=True)[
                "credit_weight"
            ].max()
            records.append(
                {
                    "record_type": "route_assignment_shape",
                    "ambiguity_stratum": stratum,
                    "route_id": str(route_id),
                    "journey_count": int(len(entropy)),
                    "mean_assignment_entropy": float(entropy.mean()),
                    "mean_maximum_assignment_weight": float(maximum.mean()),
                }
            )

        source_assignments = stratum_assignments.loc[
            stratum_assignments["route_id"].isin(PRIMARY_SOURCE_ROUTE_ORDER)
        ].copy()
        if source_assignments.empty:
            continue
        allocations = build_route_allocations(
            source_assignments,
            decision_cells,
            route_ids=PRIMARY_SOURCE_ROUTE_ORDER,
        )
        for left_route, right_route in combinations(PRIMARY_SOURCE_ROUTE_ORDER, 2):
            pair = pair_metrics_from_allocations(
                allocations, left_route, right_route, top_k
            )
            pair.update(
                {
                    "record_type": "source_route_pair",
                    "ambiguity_stratum": stratum,
                    "candidate_cell_count_stratum": stratum,
                    "journey_count": int(len(journeys)),
                    "user_count": int(journeys["user_id"].nunique()),
                }
            )
            journey_tvs = _journey_assignment_tvs(
                source_assignments, left_route, right_route, journey_ids
            )
            pair.update(
                {
                    "mean_journey_assignment_tv": float(journey_tvs.mean()) if len(journey_tvs) else np.nan,
                    "median_journey_assignment_tv": float(journey_tvs.median()) if len(journey_tvs) else np.nan,
                    "q025_journey_assignment_tv": float(journey_tvs.quantile(0.025)) if len(journey_tvs) else np.nan,
                    "q975_journey_assignment_tv": float(journey_tvs.quantile(0.975)) if len(journey_tvs) else np.nan,
                }
            )
            records.append(pair)
    return pd.DataFrame(records)


def _journey_assignment_tvs(
    assignments: pd.DataFrame,
    left_route: str,
    right_route: str,
    journey_ids: set[str],
) -> pd.Series:
    left = assignments.loc[
        assignments["route_id"].eq(left_route)
        & assignments["journey_id"].astype(str).isin(journey_ids),
        ["journey_id", "decision_cell_id", "credit_weight"],
    ]
    right = assignments.loc[
        assignments["route_id"].eq(right_route)
        & assignments["journey_id"].astype(str).isin(journey_ids),
        ["journey_id", "decision_cell_id", "credit_weight"],
    ]
    merged = left.merge(
        right,
        on=["journey_id", "decision_cell_id"],
        how="outer",
        suffixes=("_left", "_right"),
    ).fillna({"credit_weight_left": 0.0, "credit_weight_right": 0.0})
    return (
        0.5
        * (merged["credit_weight_left"] - merged["credit_weight_right"]).abs()
        .groupby(merged["journey_id"], sort=False)
        .sum()
    )

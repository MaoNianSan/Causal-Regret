from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from contracts import (
    CREDIT_TOLERANCE,
    PRIMARY_ROUTE_ORDER,
    PRIMARY_SOURCE_ROUTE_ORDER,
    ScientificInvariantError,
)


def check_pairwise_symmetry(pairwise: pd.DataFrame) -> dict[str, Any]:
    routes = list(PRIMARY_SOURCE_ROUTE_ORDER)
    matrix = pd.DataFrame(np.nan, index=routes, columns=routes, dtype=float)
    np.fill_diagonal(matrix.values, 0.0)
    for row in pairwise.itertuples(index=False):
        matrix.loc[row.route_left, row.route_right] = float(row.allocation_tv)
        matrix.loc[row.route_right, row.route_left] = float(row.allocation_tv)
    if matrix.isna().any().any():
        raise ScientificInvariantError("Pairwise allocation-TV matrix is incomplete.")
    if not np.allclose(matrix.to_numpy(), matrix.to_numpy().T, atol=1e-12, rtol=0.0):
        raise ScientificInvariantError("Pairwise allocation-TV matrix is not symmetric.")
    if not np.allclose(np.diag(matrix), 0.0, atol=1e-12, rtol=0.0):
        raise ScientificInvariantError("Pairwise allocation-TV diagonal is not zero.")
    return {"check": "pairwise_metric_symmetry", "status": "PASS"}


def validate_primary_science(
    config: dict[str, Any],
    *,
    journey_manifest: pd.DataFrame,
    decision_cells: pd.DataFrame,
    assignments: pd.DataFrame,
    route_allocations: pd.DataFrame,
    arrival_displacement: pd.DataFrame,
    source_route_pairwise: pd.DataFrame,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    retained = journey_manifest.loc[journey_manifest["is_primary_eligible"]]
    if retained.empty:
        raise ScientificInvariantError("Primary cohort is empty.")
    checks.append({"check": "primary_cohort_nonempty", "status": "PASS", "value": int(len(retained))})
    if retained["user_id"].isna().any() or retained["user_id"].astype(str).isin({"-1", "-1.0"}).any():
        raise ScientificInvariantError("Retained cohort contains invalid user IDs.")
    checks.append({"check": "valid_bootstrap_users", "status": "PASS"})
    if retained["candidate_campaign_count"].ne(1).any():
        raise ScientificInvariantError("A multi-campaign journey entered the primary cohort.")
    checks.append({"check": "unique_campaign_primary_cohort", "status": "PASS"})
    if not bool(retained["has_complete_lookback"].all()):
        raise ScientificInvariantError("An incomplete-lookback journey entered the primary cohort.")
    checks.append({"check": "complete_lookback_primary_cohort", "status": "PASS"})
    ambiguous_count = int(retained["is_attribution_ambiguous"].sum())
    if ambiguous_count <= 0:
        raise ScientificInvariantError(
            "No attribution-ambiguous journeys remain; the primary diagnostic is unsupported."
        )
    checks.append({"check": "attribution_ambiguity_present", "status": "PASS", "value": ambiguous_count})
    max_top_k = max(
        [int(config["ranking"]["primary_top_k"])]
        + [int(value) for value in config["ranking"].get("targeted_top_k", [])]
    )
    if len(decision_cells) <= max_top_k:
        raise ScientificInvariantError(
            f"Decision-cell universe={len(decision_cells)} is not larger than max top-k={max_top_k}."
        )
    checks.append({"check": "decision_cell_support_for_top_k", "status": "PASS"})
    primary_assignments = assignments.loc[assignments["route_id"].isin(PRIMARY_ROUTE_ORDER)]
    cohort_sets = {
        route_id: frozenset(
            primary_assignments.loc[
                primary_assignments["route_id"].eq(route_id), "journey_id"
            ].astype(str)
        )
        for route_id in PRIMARY_ROUTE_ORDER
    }
    if len(set(cohort_sets.values())) != 1:
        raise ScientificInvariantError("Primary routes use different journey cohorts.")
    checks.append({"check": "common_route_cohort", "status": "PASS"})
    credit_sums = (
        primary_assignments.groupby(["route_id", "journey_id"], sort=False)["credit_weight"]
        .sum()
        .sub(1.0)
        .abs()
    )
    if credit_sums.gt(CREDIT_TOLERANCE).any():
        raise ScientificInvariantError("Primary route credit conservation failed.")
    checks.append({"check": "credit_conservation", "status": "PASS"})
    single_cell_ids = set(
        retained.loc[retained["candidate_cell_count"].eq(1), "journey_id"].astype(str)
    )
    single_cell = primary_assignments.loc[
        primary_assignments["journey_id"].astype(str).isin(single_cell_ids)
        & primary_assignments["route_id"].isin(PRIMARY_SOURCE_ROUTE_ORDER)
    ]
    if single_cell_ids:
        counts = single_cell.groupby(["route_id", "journey_id"], sort=False).agg(
            assigned_cell_count=("decision_cell_id", "nunique"),
            credit_sum=("credit_weight", "sum"),
        )
        if counts["assigned_cell_count"].ne(1).any() or not np.allclose(
            counts["credit_sum"].to_numpy(dtype=float), 1.0, atol=CREDIT_TOLERANCE, rtol=0.0
        ):
            raise ScientificInvariantError("Single-cell source-route invariant failed.")
    checks.append({"check": "single_cell_source_route_invariant", "status": "PASS"})
    allocation_sums = route_allocations.groupby("route_id", sort=False)["allocation_share"].sum()
    if not np.allclose(allocation_sums.to_numpy(), 1.0, atol=1e-12, rtol=0.0):
        raise ScientificInvariantError("Route allocation vectors do not sum to one.")
    checks.append({"check": "allocation_normalization", "status": "PASS"})
    denominator_counts = route_allocations.groupby("decision_cell_id", sort=False)[
        "eligible_impression_count"
    ].nunique()
    if denominator_counts.gt(1).any():
        raise ScientificInvariantError("Ranking denominator changes across routes.")
    checks.append({"check": "common_ranking_denominator", "status": "PASS"})
    if arrival_displacement["allocation_tv_vs_arrival"].lt(-1e-12).any() or arrival_displacement[
        "allocation_tv_vs_arrival"
    ].gt(1.0 + 1e-12).any():
        raise ScientificInvariantError("Arrival allocation TV is outside [0,1].")
    checks.append({"check": "arrival_tv_range", "status": "PASS"})
    checks.append(check_pairwise_symmetry(source_route_pairwise))
    return checks

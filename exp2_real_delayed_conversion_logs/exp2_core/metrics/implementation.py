from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

from contracts import (
    METRIC_TOLERANCE,
    PRIMARY_ROUTE_ORDER,
    PRIMARY_SOURCE_ROUTE_ORDER,
    ScientificInvariantError,
)


@dataclass(frozen=True)
class PairwiseMetricState:
    route_left: str
    route_right: str
    support_cell_ids: tuple[str, ...]


@dataclass(frozen=True)
class MetricResult:
    route_allocations: pd.DataFrame
    arrival_displacement: pd.DataFrame
    source_route_pairwise: pd.DataFrame
    kendall_support: pd.DataFrame
    ambiguity_strata: pd.DataFrame
    kendall_metric_states: tuple[PairwiseMetricState, ...]


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


def stable_top_k(route_frame: pd.DataFrame, top_k: int) -> tuple[str, ...]:
    if top_k <= 0:
        raise ScientificInvariantError("top_k must be positive.")
    if top_k >= len(route_frame):
        raise ScientificInvariantError(
            f"top_k={top_k} must be strictly smaller than cell universe={len(route_frame)}."
        )
    ordered = route_frame.sort_values(
        ["source_time_credit_score", "campaign_id", "source_date_utc", "decision_cell_id"],
        ascending=[False, True, True, True],
        kind="stable",
    )
    return tuple(ordered.head(top_k)["decision_cell_id"].astype(str))


def top_k_overlap(left: Iterable[str], right: Iterable[str], top_k: int) -> float:
    left_set = set(left)
    right_set = set(right)
    return len(left_set.intersection(right_set)) / float(top_k)


def kendall_tau_b(
    left_frame: pd.DataFrame,
    right_frame: pd.DataFrame,
    *,
    support_cell_ids: Iterable[str] | None = None,
) -> tuple[float, dict[str, int]]:
    merged = left_frame[
        ["decision_cell_id", "source_time_credit_score", "credited_conversion_mass"]
    ].merge(
        right_frame[
            ["decision_cell_id", "source_time_credit_score", "credited_conversion_mass"]
        ],
        on="decision_cell_id",
        how="inner",
        suffixes=("_left", "_right"),
        validate="one_to_one",
    )
    if support_cell_ids is None:
        active = merged.loc[
            merged["credited_conversion_mass_left"].gt(0)
            | merged["credited_conversion_mass_right"].gt(0)
        ].copy()
    else:
        support_ids = tuple(str(value) for value in support_cell_ids)
        if len(support_ids) != len(set(support_ids)):
            raise ScientificInvariantError("Frozen Kendall support contains duplicate cell IDs.")
        indexed = merged.assign(
            decision_cell_id=merged["decision_cell_id"].astype(str)
        ).set_index("decision_cell_id", drop=False)
        missing = sorted(set(support_ids).difference(indexed.index))
        if missing:
            raise ScientificInvariantError(
                f"Frozen Kendall support contains cells outside the common universe: {missing[:10]}"
            )
        active = indexed.loc[list(support_ids)].reset_index(drop=True)
    support = {
        "common_active_cell_count": int(len(active)),
        "left_positive_credit_cell_count": int(
            merged["credited_conversion_mass_left"].gt(0).sum()
        ),
        "right_positive_credit_cell_count": int(
            merged["credited_conversion_mass_right"].gt(0).sum()
        ),
        "common_positive_credit_cell_count": int(
            (
                merged["credited_conversion_mass_left"].gt(0)
                & merged["credited_conversion_mass_right"].gt(0)
            ).sum()
        ),
    }
    if len(active) < 2:
        return float("nan"), support
    result = kendalltau(
        active["source_time_credit_score_left"].to_numpy(dtype=float),
        active["source_time_credit_score_right"].to_numpy(dtype=float),
        variant="b",
        nan_policy="omit",
    )
    return float(result.statistic), support


def _route_frame(allocations: pd.DataFrame, route_id: str) -> pd.DataFrame:
    frame = allocations.loc[allocations["route_id"].eq(route_id)].copy()
    if frame.empty:
        raise ScientificInvariantError(f"Missing route allocation: {route_id}")
    return frame.sort_values("decision_cell_id", kind="stable").reset_index(drop=True)


def build_pairwise_metric_state(
    allocations: pd.DataFrame,
    left_route: str,
    right_route: str,
) -> PairwiseMetricState:
    left = _route_frame(allocations, left_route)
    right = _route_frame(allocations, right_route)
    if not left["decision_cell_id"].equals(right["decision_cell_id"]):
        raise ScientificInvariantError("Pairwise routes do not share the same decision-cell universe.")
    active = left["credited_conversion_mass"].gt(0) | right[
        "credited_conversion_mass"
    ].gt(0)
    support_cell_ids = tuple(left.loc[active, "decision_cell_id"].astype(str))
    if len(support_cell_ids) < 2:
        raise ScientificInvariantError(
            f"Kendall support for {left_route} vs {right_route} has fewer than two cells."
        )
    return PairwiseMetricState(
        route_left=left_route,
        route_right=right_route,
        support_cell_ids=support_cell_ids,
    )


def _pair_metrics_from_allocations(
    allocations: pd.DataFrame,
    left_route: str,
    right_route: str,
    top_k: int,
    *,
    metric_state: PairwiseMetricState | None = None,
) -> dict[str, float | int | str]:
    left = _route_frame(allocations, left_route)
    right = _route_frame(allocations, right_route)
    if not left["decision_cell_id"].equals(right["decision_cell_id"]):
        raise ScientificInvariantError("Pairwise routes do not share the same decision-cell universe.")
    tv = allocation_tv(
        left["allocation_share"].to_numpy(dtype=float),
        right["allocation_share"].to_numpy(dtype=float),
    )
    left_top = stable_top_k(left, top_k)
    right_top = stable_top_k(right, top_k)
    overlap = top_k_overlap(left_top, right_top, top_k)
    if metric_state is None:
        metric_state = build_pairwise_metric_state(allocations, left_route, right_route)
    if (metric_state.route_left, metric_state.route_right) != (left_route, right_route):
        raise ScientificInvariantError("Frozen Kendall support is attached to the wrong route pair.")
    tau, support = kendall_tau_b(
        left,
        right,
        support_cell_ids=metric_state.support_cell_ids,
    )
    return {
        "route_left": left_route,
        "route_right": right_route,
        "allocation_tv": tv,
        "top_k": int(top_k),
        "top_k_overlap": overlap,
        "top_k_set_disagreement": 1.0 - overlap,
        "kendall_tau_b": tau,
        **support,
    }


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


def compute_primary_metrics(
    assignments: pd.DataFrame,
    decision_cells: pd.DataFrame,
    journey_manifest: pd.DataFrame,
    *,
    top_k: int,
) -> MetricResult:
    allocations = build_route_allocations(assignments, decision_cells)

    arrival_rows: list[dict[str, float | int | str]] = []
    metric_states: list[PairwiseMetricState] = []
    for route_id in PRIMARY_SOURCE_ROUTE_ORDER:
        metric_state = build_pairwise_metric_state(
            allocations, "arrival_time_accounting_anchor", route_id
        )
        metric_states.append(metric_state)
        row = _pair_metrics_from_allocations(
            allocations,
            "arrival_time_accounting_anchor",
            route_id,
            top_k,
            metric_state=metric_state,
        )
        arrival_rows.append(
            {
                "route_id": route_id,
                "allocation_tv_vs_arrival": row["allocation_tv"],
                "top_k": row["top_k"],
                "top_k_overlap_vs_arrival": row["top_k_overlap"],
                "top_k_set_disagreement": row["top_k_set_disagreement"],
                "kendall_tau_b_vs_arrival": row["kendall_tau_b"],
                "common_active_cell_count": row["common_active_cell_count"],
                "positive_credit_cell_count": int(
                    _route_frame(allocations, route_id)["positive_credit"].sum()
                ),
            }
        )
    arrival_displacement = pd.DataFrame(arrival_rows)

    pair_rows: list[dict[str, float | int | str]] = []
    support_rows: list[dict[str, float | int | str]] = []
    for left_route, right_route in combinations(PRIMARY_SOURCE_ROUTE_ORDER, 2):
        metric_state = build_pairwise_metric_state(
            allocations, left_route, right_route
        )
        metric_states.append(metric_state)
        row = _pair_metrics_from_allocations(
            allocations,
            left_route,
            right_route,
            top_k,
            metric_state=metric_state,
        )
        row["mean_journey_assignment_tv"] = compute_mean_journey_assignment_tv(
            assignments, left_route, right_route
        )
        pair_rows.append(row)
        support_rows.append(
            {
                key: row[key]
                for key in (
                    "route_left",
                    "route_right",
                    "kendall_tau_b",
                    "common_active_cell_count",
                    "left_positive_credit_cell_count",
                    "right_positive_credit_cell_count",
                    "common_positive_credit_cell_count",
                )
            }
        )
    source_pairwise = pd.DataFrame(pair_rows)
    kendall_support = pd.DataFrame(support_rows)

    ambiguity = compute_ambiguity_strata_metrics(
        assignments,
        decision_cells,
        journey_manifest,
        top_k=top_k,
    )
    return MetricResult(
        route_allocations=allocations,
        arrival_displacement=arrival_displacement,
        source_route_pairwise=source_pairwise,
        kendall_support=kendall_support,
        ambiguity_strata=ambiguity,
        kendall_metric_states=tuple(metric_states),
    )


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
        # Route-level entropy and concentration.
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
            pair = _pair_metrics_from_allocations(
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


def compute_targeted_top_k_metrics(
    allocations: pd.DataFrame,
    top_k_values: Iterable[int],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for top_k in top_k_values:
        for route_id in PRIMARY_SOURCE_ROUTE_ORDER:
            record = _pair_metrics_from_allocations(
                allocations, "arrival_time_accounting_anchor", route_id, int(top_k)
            )
            record.update(
                {
                    "analysis_tier": "targeted",
                    "targeted_dimension": "top_k",
                    "targeted_value": int(top_k),
                    "record_type": "arrival_displacement",
                    "route_id": route_id,
                }
            )
            rows.append(record)
        for left_route, right_route in combinations(PRIMARY_SOURCE_ROUTE_ORDER, 2):
            record = _pair_metrics_from_allocations(
                allocations, left_route, right_route, int(top_k)
            )
            record.update(
                {
                    "analysis_tier": "targeted",
                    "targeted_dimension": "top_k",
                    "targeted_value": int(top_k),
                    "record_type": "source_route_pair",
                    "route_id": pd.NA,
                }
            )
            rows.append(record)
    return pd.DataFrame(rows)

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

import pandas as pd

from contracts import PRIMARY_SOURCE_ROUTE_ORDER

from .allocation import build_route_allocations
from .ambiguity import compute_ambiguity_strata_metrics, compute_mean_journey_assignment_tv
from .ranking import (
    PairwiseMetricState,
    _route_frame,
    build_pairwise_metric_state,
    pair_metrics_from_allocations,
)


@dataclass(frozen=True)
class MetricResult:
    route_allocations: pd.DataFrame
    arrival_displacement: pd.DataFrame
    source_route_pairwise: pd.DataFrame
    kendall_support: pd.DataFrame
    ambiguity_strata: pd.DataFrame
    kendall_metric_states: tuple[PairwiseMetricState, ...]


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
        row = pair_metrics_from_allocations(
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
        row = pair_metrics_from_allocations(
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


def compute_targeted_top_k_metrics(
    allocations: pd.DataFrame,
    top_k_values: Iterable[int],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for top_k in top_k_values:
        for route_id in PRIMARY_SOURCE_ROUTE_ORDER:
            record = pair_metrics_from_allocations(
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
            record = pair_metrics_from_allocations(
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

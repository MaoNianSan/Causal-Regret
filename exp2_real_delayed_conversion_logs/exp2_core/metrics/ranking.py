from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
from scipy.stats import kendalltau

from contracts import ScientificInvariantError

from .allocation import allocation_tv


@dataclass(frozen=True)
class PairwiseMetricState:
    route_left: str
    route_right: str
    support_cell_ids: tuple[str, ...]


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


def pair_metrics_from_allocations(
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

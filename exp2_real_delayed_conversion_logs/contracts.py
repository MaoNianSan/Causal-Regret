from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Iterable

EXPERIMENT_ID: Final[str] = "exp2"
EXPERIMENT_SLUG: Final[str] = "delayed_conversion_attribution"
EXPERIMENT_TITLE: Final[str] = "Attribution Sensitivity in Delayed-Conversion Logs"

SECONDS_PER_DAY: Final[float] = 86_400.0
CREDIT_TOLERANCE: Final[float] = 1e-10
METRIC_TOLERANCE: Final[float] = 1e-12
MAXIMUM_KENDALL_NAN_FRACTION: Final[float] = 0.05


class Exp2Error(RuntimeError):
    """Base exception for Experiment 2."""


class ConfigurationError(Exp2Error):
    """Raised when the frozen experiment specification is violated."""


class DataContractError(Exp2Error):
    """Raised when the input data cannot support the declared analysis."""


class ScientificInvariantError(Exp2Error):
    """Raised when a scientific invariant is violated."""


@dataclass(frozen=True)
class RouteSpec:
    route_id: str
    display_label: str
    route_role: str
    analysis_tier: str
    source_bound: bool
    deployable: bool
    ground_truth: bool


ROUTE_SPECS: Final[dict[str, RouteSpec]] = {
    "arrival_bin_anchor": RouteSpec(
        route_id="arrival_bin_anchor",
        display_label="Arrival-time anchor",
        route_role="diagnostic_anchor",
        analysis_tier="primary",
        source_bound=False,
        deployable=False,
        ground_truth=False,
    ),
    "first_touch": RouteSpec(
        route_id="first_touch",
        display_label="First click or touch",
        route_role="primary_source_route",
        analysis_tier="primary",
        source_bound=True,
        deployable=False,
        ground_truth=False,
    ),
    "last_touch": RouteSpec(
        route_id="last_touch",
        display_label="Last click or touch",
        route_role="primary_source_route",
        analysis_tier="primary",
        source_bound=True,
        deployable=False,
        ground_truth=False,
    ),
    "linear_credit": RouteSpec(
        route_id="linear_credit",
        display_label="Linear attribution",
        route_role="primary_source_route",
        analysis_tier="primary",
        source_bound=True,
        deployable=False,
        ground_truth=False,
    ),
    "time_decay_credit": RouteSpec(
        route_id="time_decay_credit",
        display_label="Time-decay attribution",
        route_role="primary_source_route",
        analysis_tier="primary",
        source_bound=True,
        deployable=False,
        ground_truth=False,
    ),
    "em_soft_credit": RouteSpec(
        route_id="em_soft_credit",
        display_label="EM soft attribution",
        route_role="appendix_diagnostic",
        analysis_tier="appendix",
        source_bound=False,
        deployable=False,
        ground_truth=False,
    ),
    "logged_attribution_reference": RouteSpec(
        route_id="logged_attribution_reference",
        display_label="Logged attribution reference",
        route_role="audit_reference",
        analysis_tier="appendix",
        source_bound=True,
        deployable=False,
        ground_truth=False,
    ),
}

PRIMARY_ROUTE_ORDER: Final[tuple[str, ...]] = (
    "arrival_bin_anchor",
    "first_touch",
    "last_touch",
    "linear_credit",
    "time_decay_credit",
)

PRIMARY_SOURCE_ROUTE_ORDER: Final[tuple[str, ...]] = (
    "first_touch",
    "last_touch",
    "linear_credit",
    "time_decay_credit",
)

ALL_ROUTE_ORDER: Final[tuple[str, ...]] = (
    *PRIMARY_ROUTE_ORDER,
    "em_soft_credit",
    "logged_attribution_reference",
)

REQUIRED_RAW_LOGICAL_COLUMNS: Final[tuple[str, ...]] = (
    "timestamp",
    "uid",
    "campaign",
    "conversion",
    "conversion_timestamp",
    "conversion_id",
    "attribution",
    "click",
)

JOURNEY_REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "journey_id",
    "user_id",
    "conversion_id",
    "conversion_timestamp_utc",
    "candidate_event_count",
    "candidate_cell_count",
    "candidate_campaign_count",
    "is_attribution_ambiguous",
    "is_attribution_degenerate",
    "is_primary_eligible",
    "exclusion_reason",
    "arrival_anchor_cell_id",
)

DECISION_CELL_REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "decision_cell_id",
    "campaign_id",
    "source_date_utc",
    "eligible_impression_count",
    "eligible_journey_count",
    "is_support_eligible",
)

ASSIGNMENT_REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "journey_id",
    "route_id",
    "decision_cell_id",
    "credit_weight",
    "analysis_tier",
    "route_role",
)

DISALLOWED_RESULT_TERMS: Final[tuple[str, ...]] = (
    "causal_regret",
    "policy_value",
    "policy_utility",
    "roi",
    "profit",
    "uplift",
    "ground_truth",
    "oracle_value",
)


def require_columns(columns: Iterable[str], required: Iterable[str], *, context: str) -> None:
    available = set(columns)
    missing = [column for column in required if column not in available]
    if missing:
        raise DataContractError(f"{context}: missing required columns: {missing}")


def route_display_label(route_id: str) -> str:
    try:
        return ROUTE_SPECS[route_id].display_label
    except KeyError as exc:
        raise ConfigurationError(f"Unknown route_id={route_id!r}") from exc


def validate_route_ids(route_ids: Iterable[str]) -> tuple[str, ...]:
    route_ids = tuple(route_ids)
    unknown = [route_id for route_id in route_ids if route_id not in ROUTE_SPECS]
    if unknown:
        raise ConfigurationError(f"Unknown route IDs: {unknown}")
    if len(set(route_ids)) != len(route_ids):
        raise ConfigurationError("Route IDs must be unique.")
    return route_ids

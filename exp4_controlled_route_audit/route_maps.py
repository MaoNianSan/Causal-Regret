"""Deprecated compatibility exports for v2 route and metric APIs."""

from exp4.metrics.action_gaps import (
    ActionGapDefectResult,
    action_pair_indices,
    compute_action_gap_defect,
    compute_action_gaps,
)
from exp4.routes.appendix_routes import (
    construct_arrival_time_route,
    construct_history_surrogate_route,
)
from exp4.routes.common import candidate_sources, compute_candidate_weights
from exp4.routes.partial_label_proxy import (
    AttributionDiagnostics,
    construct_partial_label_proxy_route,
)
from exp4.routes.source_bound import RouteMapResult, construct_source_bound_route

construct_proxy_label_route = construct_partial_label_proxy_route

__all__ = [
    "ActionGapDefectResult",
    "AttributionDiagnostics",
    "RouteMapResult",
    "action_pair_indices",
    "candidate_sources",
    "compute_action_gap_defect",
    "compute_action_gaps",
    "compute_candidate_weights",
    "construct_arrival_time_route",
    "construct_history_surrogate_route",
    "construct_partial_label_proxy_route",
    "construct_proxy_label_route",
    "construct_source_bound_route",
]

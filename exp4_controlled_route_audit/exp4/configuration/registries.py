"""Stable machine identifiers and paper-facing names."""

from __future__ import annotations

from typing import Any


ROUTE_ORDER = ("proxy_label", "source_bound", "arrival_time", "history_surrogate")
ROUTE_REGISTRY: dict[str, dict[str, Any]] = {
    "proxy_label": {
        "display_name": "Partial-label proxy attribution",
        "analysis_role": "primary_route",
        "uses_source_labels": "partial",
        "uses_future_information": False,
    },
    "source_bound": {
        "display_name": "Source-bound reference",
        "analysis_role": "controlled_invariant",
        "uses_source_labels": True,
        "uses_future_information": False,
    },
    "arrival_time": {
        "display_name": "Arrival-time assignment",
        "analysis_role": "appendix_regression",
        "uses_source_labels": False,
        "uses_future_information": False,
    },
    "history_surrogate": {
        "display_name": "History-surrogate route",
        "analysis_role": "appendix_regression",
        "uses_source_labels": False,
        "uses_future_information": False,
    },
}

AUDIT_DESIGN_ORDER = (
    "mcar_unweighted",
    "ambiguity_selective_unweighted",
    "ambiguity_selective_ipw",
    "full_population",
)
AUDIT_DESIGN_REGISTRY = {
    "mcar_unweighted": {
        "display_name": "MCAR, unweighted",
        "inclusion_mechanism": "mcar",
        "weighting_method": "unweighted",
    },
    "ambiguity_selective_unweighted": {
        "display_name": "Ambiguity-selective, unweighted",
        "inclusion_mechanism": "ambiguity_selective",
        "weighting_method": "unweighted",
    },
    "ambiguity_selective_ipw": {
        "display_name": "Ambiguity-selective, IPW",
        "inclusion_mechanism": "ambiguity_selective",
        "weighting_method": "hajek_ipw",
    },
    "full_population": {
        "display_name": "Full-population audit",
        "inclusion_mechanism": "full_population",
        "weighting_method": "unweighted",
    },
}

CONTROL_ORDER = (
    "affine_linked",
    "blocked_correspondence_destroyed",
    "nonlinear_monotone",
)
CONTROL_REGISTRY = {
    "affine_linked": {
        "display_name": "Affine-linked control",
        "analysis_tier": "primary",
        "correspondence": "preserved by construction",
    },
    "blocked_correspondence_destroyed": {
        "display_name": "Temporally blocked correspondence-destroyed control",
        "analysis_tier": "primary",
        "correspondence": "destroyed within temporal blocks",
    },
    "nonlinear_monotone": {
        "display_name": "Nonlinear monotone control",
        "analysis_tier": "appendix",
        "correspondence": "monotone but outside affine family",
    },
}

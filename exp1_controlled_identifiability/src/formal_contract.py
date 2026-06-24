from __future__ import annotations

"""Backward-compatible aliases for the current EXP1 manuscript contract.

Deprecated pre-redesign setting identifiers are intentionally absent.  New code
should import from :mod:`src.experiment_contract`.
"""

from src.experiment_contract import (
    EXPERIMENT_ID,
    METHOD_SPECS,
    SETTING_DISPLAY_NAMES,
    method_spec,
)

FORMAL_SETTINGS = list(SETTING_DISPLAY_NAMES)
FORMAL_METHOD_ORDER = [
    "arrival_time_naive",
    "delayed_exp3",
    "source_labelled",
    "soft_attribution_em",
    "proxy_state",
    "oracle_reference",
]
FORMAL_METHOD_DISPLAY_NAME = {
    spec.method_id: spec.method_display_name
    for spec in METHOD_SPECS.values()
}
INTERNAL_METHOD_MAP = {
    internal: spec.method_id
    for internal, spec in METHOD_SPECS.items()
}
METHOD_ROLES = {
    spec.method_id: {
        "information_interface": spec.information_interface,
        "reference_role": spec.reference_role,
        "diagnostic_only": spec.diagnostic_only,
        "deployable": spec.deployable,
    }
    for spec in METHOD_SPECS.values()
}

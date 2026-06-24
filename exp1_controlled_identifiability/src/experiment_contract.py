from __future__ import annotations

"""Canonical EXP1 output and manuscript-interface contract.

The simulation backend uses compact internal method identifiers.  This module
maps them to stable manuscript-facing identifiers and records the information
interface required by every result, table, and figure row.
"""

from dataclasses import dataclass
from typing import Mapping

EXPERIMENT_ID = "exp1_controlled_validity"
N_BOOTSTRAP = 2000
CI_LEVEL = 0.95
PRIMARY_METRIC = "causal_regret_per_round"
PRIMARY_METRIC_FORMULA = "R_T^c / T"
PRIMARY_HORIZON = "T_5000"
PRIMARY_OUTCOME_ID = "state_dependent_squared_loss"
INPUT_DATA_STATUS = "synthetic_complete"


@dataclass(frozen=True)
class MethodSpec:
    method_id: str
    method_display_name: str
    information_interface: str
    reference_role: str
    diagnostic_only: bool
    deployable: bool


METHOD_SPECS: Mapping[str, MethodSpec] = {
    "oracle": MethodSpec(
        "oracle_reference",
        "Context oracle reference",
        "oracle_reference",
        "oracle_reference",
        False,
        False,
    ),
    "naive": MethodSpec(
        "arrival_time_naive", "Arrival time", "arrival_time", "none", False, True
    ),
    "naive_ewma": MethodSpec(
        "arrival_time_ewma",
        "Arrival time with EWMA",
        "arrival_time",
        "none",
        False,
        True,
    ),
    "delayed_ucb": MethodSpec(
        "delayed_ucb", "Delayed UCB", "unlabelled_delayed", "none", False, True
    ),
    "delayed_exp3": MethodSpec(
        "delayed_exp3", "Delayed EXP3", "unlabelled_delayed", "none", False, True
    ),
    "sliding_window_W250": MethodSpec(
        "arrival_time_sliding_window_w250",
        "Arrival time sliding window",
        "arrival_time",
        "none",
        False,
        True,
    ),
    "anonymous_delayed": MethodSpec(
        "anonymous_delayed",
        "Anonymous delayed",
        "unlabelled_delayed",
        "none",
        False,
        True,
    ),
    "causal_labeled": MethodSpec(
        "source_labelled", "Source labelled", "source_labelled", "none", False, True
    ),
    "causal_em": MethodSpec(
        "soft_attribution_em",
        "Soft attribution EM",
        "partial_attribution",
        "none",
        False,
        True,
    ),
    "causal_em_misspecified": MethodSpec(
        "soft_attribution_em_stationary_ablation",
        "Stationary geometric EM ablation",
        "partial_attribution",
        "diagnostic_control",
        True,
        False,
    ),
    "proxy": MethodSpec(
        "proxy_state", "Filtered state proxy", "proxy_state", "none", False, True
    ),
}

SETTING_DISPLAY_NAMES: Mapping[str, str] = {
    "zero_static": "Zero delay",
    "aligned_static_delay_15": "Aligned static delay 15",
    "geometric_matched_15": "Geometric matched delay 15",
    "mixture_matched_15": "Mixture matched delay 15",
    "state_structural_matched_15": "State structural matched delay 15",
    "proxy_good_matched_15": "Good proxy matched delay 15",
    "proxy_bad_matched_15": "Bad proxy matched delay 15",
    "action_structural_stress": "Action structural stress test",
}


def subexperiment_id(setting_role: str) -> str:
    return {
        "static_alignment": "source_binding_validity",
        "matched_primary": "matched_mean_delay",
        "proxy_quality": "proxy_quality_diagnostic",
        "policy_dependent_stress": "policy_dependent_stress_test",
    }.get(str(setting_role), "controlled_delay")


def method_spec(internal_method: str) -> MethodSpec:
    try:
        return METHOD_SPECS[str(internal_method)]
    except KeyError as exc:
        raise KeyError(
            f"No EXP1 contract mapping for internal method {internal_method!r}."
        ) from exc

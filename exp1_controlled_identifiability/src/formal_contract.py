from __future__ import annotations

EXPERIMENT_ID = "exp1_controlled_validity"

PANEL_A_SETTINGS = [
    "zero_static",
    "aligned_static_delay_15",
    "geometric_mid",
    "mixture_mid",
    "structural_mid",
]

PANEL_B_SETTINGS = [
    "matched_geometric_target_15",
    "matched_mixture_target_15",
    "matched_structural_target_15",
]

FORMAL_SETTINGS = PANEL_A_SETTINGS + PANEL_B_SETTINGS

FORMAL_METHOD_ORDER = [
    "arrival_time_naive",
    "delayed_exp3",
    "source_labelled",
    "soft_attribution_em",
    "proxy_state",
    "oracle_reference",
]

FORMAL_METHOD_DISPLAY_NAME = {
    "arrival_time_naive": "Arrival time",
    "delayed_exp3": "Delayed EXP3",
    "source_labelled": "Source labelled",
    "soft_attribution_em": "Soft attribution",
    "proxy_state": "Proxy state",
    "oracle_reference": "Oracle reference\u2020",
}

INTERNAL_METHOD_MAP = {
    "naive": "arrival_time_naive",
    "delayed_exp3": "delayed_exp3",
    "causal_labeled": "source_labelled",
    "causal_em": "soft_attribution_em",
    "proxy": "proxy_state",
    "oracle": "oracle_reference",
}

FORMAL_METHOD_TO_INTERNAL = {
    "arrival_time_naive": ("unlabelled", "naive"),
    "delayed_exp3": ("unlabelled", "delayed_exp3"),
    "source_labelled": ("labelled", "causal_labeled"),
    "soft_attribution_em": ("mixture_labelled", "causal_em"),
    "proxy_state": ("unlabelled", "proxy"),
    "oracle_reference": ("labelled", "oracle"),
}

METHOD_ROLES = {
    "arrival_time_naive": {
        "information_interface": "arrival_time",
        "reference_role": "none",
        "diagnostic_only": False,
        "deployable": True,
    },
    "delayed_exp3": {
        "information_interface": "unlabelled_delayed",
        "reference_role": "none",
        "diagnostic_only": False,
        "deployable": True,
    },
    "source_labelled": {
        "information_interface": "source_labelled",
        "reference_role": "none",
        "diagnostic_only": False,
        "deployable": True,
    },
    "soft_attribution_em": {
        "information_interface": "partial_attribution",
        "reference_role": "none",
        "diagnostic_only": False,
        "deployable": True,
    },
    "proxy_state": {
        "information_interface": "proxy_state",
        "reference_role": "none",
        "diagnostic_only": False,
        "deployable": True,
    },
    "oracle_reference": {
        "information_interface": "oracle_reference",
        "reference_role": "oracle_reference",
        "diagnostic_only": False,
        "deployable": False,
    },
}

PANEL_A_LABELS = {
    "zero_static": "No delay\n(static state)",
    "aligned_static_delay_15": "Fixed delay = 15\n(static state)",
    "geometric_mid": "Geometric\ndelay",
    "mixture_mid": "Mixture\ndelay",
    "structural_mid": "Structural\ndelay",
}

SETTING_DISPLAY_NAMES = {
    **PANEL_A_LABELS,
    "matched_geometric_target_15": "Geometric",
    "matched_mixture_target_15": "Mixture",
    "matched_structural_target_15": "Structural",
}

SOURCE_BINDING_CLASS = {
    "zero_static": "source_preserving",
    "aligned_static_delay_15": "source_preserving",
    "geometric_mid": "source_disrupting",
    "mixture_mid": "source_disrupting",
    "structural_mid": "source_disrupting",
    "matched_geometric_target_15": "source_disrupting",
    "matched_mixture_target_15": "source_disrupting",
    "matched_structural_target_15": "source_disrupting",
}

OLD_METHOD_IDS = {
    "no_causal",
    "no_rnn",
    "soft_attribution",
    "causal_labeled",
    "causal_em",
    "naive",
    "oracle",
    "delayed_ucb",
    "sliding_window_w250",
    "sliding_window_W250",
    "anonymous_delayed",
}


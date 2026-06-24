"""Configuration for Experiment 4: a controlled recoverability-boundary stress test."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = BASE_DIR / "outputs" / "runs"

EXPERIMENT_ID = "exp4_recoverability_boundary"
EXPERIMENT_DISPLAY_NAME = "Source-label sufficiency and proxy-only recovery limitation"

SEEDS_FULL = list(range(30))
SEEDS_FAST = SEEDS_FULL[:3]
FULL_T = 5000
FAST_T = FULL_T

K_ACTIONS = 10
STATE_DIM = 3
WARMUP_T = 250
TARGET_MEAN_DELAY = 2
MAX_DELAY = 20
DEFAULT_BETA = 2.0
DEFAULT_PROXY_SIGMA = 0.25
CONTEXT_PROXY_SIGMA = 0.25

PROXY_SIGMAS = [0.05, 0.10, 0.25, 0.50, 1.00]
Q_GRID = [0.00, 0.10, 0.30, 0.50, 0.70, 1.00]
BETA_GRID = [0.00, 0.25, 0.50, 1.00, 1.50, 2.00, 3.00]

BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 20260622
CI_LEVEL = 0.95

PAPER_FIGURE_WIDTH_IN = 6.85
PAPER_DPI = 600
AXIS_LABEL_FONT_SIZE = 8.5
TICK_FONT_SIZE = 7.5
LEGEND_FONT_SIZE = 7.0
PANEL_LABEL_FONT_SIZE = 9.0
LINE_WIDTH = 1.2
MARKER_SIZE = 4.0
CI_ALPHA = 0.15

# Tasks are intentionally split by condition.  All paths are deterministic by seed,
# so shared comparisons use the exact same latent state and delay realization.
N_TASKS_PER_SEED = 1 + len(Q_GRID) + len(Q_GRID) * len(PROXY_SIGMAS) + len(BETA_GRID)

METHOD_REGISTRY = {
    "arrival_time_naive": {
        "display": "Arrival time",
        "information_interface": "arrival_time",
        "reference_role": "none",
        "diagnostic_only": False,
        "deployable": True,
        "uses_arrival_feedback": True,
        "uses_source_labels": False,
        "uses_proxy": "coarse_context_only",
        "description": "Assigns anonymous arrival losses to the current action and current proxy context.",
    },
    "observable_history_surrogate": {
        "display": "Observable history surrogate",
        "information_interface": "observable_history_proxy",
        "reference_role": "none",
        "diagnostic_only": False,
        "deployable": True,
        "uses_arrival_feedback": True,
        "uses_source_labels": False,
        "uses_proxy": "coarse_context_only",
        "description": "Uses exponentially discounted anonymous arrival history within the common observable proxy context.",
    },
    "proxy_label_recovery": {
        "display": "Proxy label recovery",
        "information_interface": "partial_attribution_proxy",
        "reference_role": "none",
        "diagnostic_only": False,
        "deployable": True,
        "uses_arrival_feedback": True,
        "uses_source_labels": "partial",
        "uses_proxy": "candidate_source_similarity",
        "description": "Uses exact retained source labels and soft proxy-based attribution for anonymous arrivals.",
    },
    "source_labelled_reference": {
        "display": "Source labelled reference",
        "information_interface": "source_labelled",
        "reference_role": "source_labelled_reference",
        "diagnostic_only": False,
        "deployable": False,
        "uses_arrival_feedback": True,
        "uses_source_labels": True,
        "uses_proxy": "coarse_context_only",
        "description": "Reference route with every arriving outcome linked to its source action and source proxy context.",
    },
    "proxy_noisy_oracle_diagnostic": {
        "display": "Noisy oracle proxy",
        "information_interface": "diagnostic_proxy_measurement",
        "reference_role": "diagnostic_control",
        "diagnostic_only": True,
        "deployable": False,
        "uses_arrival_feedback": False,
        "uses_source_labels": False,
        "uses_proxy": "instantaneous_noisy_measurement",
        "description": "Diagnostic policy that maps the emitted noisy proxy directly to the nearest action center.",
    },
    "proxy_oracle_diagnostic": {
        "display": "Proxy oracle diagnostic",
        "information_interface": "latent_oracle",
        "reference_role": "oracle_reference",
        "diagnostic_only": True,
        "deployable": False,
        "uses_arrival_feedback": False,
        "uses_source_labels": False,
        "uses_proxy": "latent_state",
        "description": "Diagnostic upper benchmark using the latent decision-time state; never a deployable method.",
    },
}

PRIMARY_FIGURE_STEMS = ["fig_exp4_recoverability_boundary"]
APPENDIX_FIGURE_STEMS = ["fig_app_exp4_delay_state_coupling"]


def auto_workers(mode: str) -> int:
    """Use all visible CPUs up to 16 for local fast and 32 for cloud full."""
    cap = 16 if mode == "fast" else 32
    return max(1, min(os.cpu_count() or 1, cap))


def mode_settings(mode: str) -> tuple[list[int], int]:
    if mode == "fast":
        return SEEDS_FAST, FAST_T
    if mode == "full":
        return SEEDS_FULL, FULL_T
    raise ValueError(f"unknown mode: {mode}")


def method_spec(method_id: str) -> dict:
    try:
        return METHOD_REGISTRY[method_id]
    except KeyError as exc:
        raise KeyError(f"unknown method id: {method_id}") from exc

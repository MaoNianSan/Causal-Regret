"""Frozen configuration for Experiment 4.

Experiment 4 separates controlled route alignment from the reliability of an
 evidence-qualified audit.  Stable machine identifiers are intentionally kept
separate from manuscript display names and analytical roles.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = BASE_DIR / "outputs" / "runs"

EXPERIMENT_ID = "exp4_controlled_route_audit"
EXPERIMENT_DISPLAY_NAME = "Controlled Route Alignment and Evidence-Qualified Audit"
RESULT_SCHEMA = "exp4_controlled_route_audit_v1"
LEGACY_RESULT_SCHEMA = "legacy_exp4_v1"

MODULE_ROUTE_BOUNDARY = "route_boundary"
MODULE_AUDIT_RELIABILITY = "audit_reliability"
MODULE_CALIBRATION_CONTROL = "calibration_control"
MODULE_LEARNER_APPENDIX = "learner_consequence_appendix"

ROUTE_ORDER = ["arrival_time", "history_surrogate", "proxy_label", "source_bound"]
ROUTE_REGISTRY: dict[str, dict[str, Any]] = {
    "arrival_time": {
        "route_display_name": "Arrival time",
        "information_interface": "arrival_clock_assignment",
        "analysis_role": "operational_baseline",
        "reference_role": "none",
        "is_deployable": False,
        "uses_source_labels": False,
        "uses_latent_information": False,
        "uses_future_information": False,
        "simulator_only_full_map": True,
    },
    "history_surrogate": {
        "route_display_name": "History surrogate",
        "information_interface": "anonymous_observable_history",
        "analysis_role": "operational_baseline",
        "reference_role": "none",
        "is_deployable": False,
        "uses_source_labels": False,
        "uses_latent_information": False,
        "uses_future_information": False,
        "simulator_only_full_map": True,
    },
    "proxy_label": {
        "route_display_name": "Proxy-label",
        "information_interface": "partial_source_labels_and_proxy_attribution",
        "analysis_role": "primary_route",
        "reference_role": "none",
        "is_deployable": False,
        "uses_source_labels": "partial",
        "uses_latent_information": False,
        "uses_future_information": False,
        "simulator_only_full_map": True,
    },
    "source_bound": {
        "route_display_name": "Source-labelled",
        "information_interface": "source_bound",
        "analysis_role": "diagnostic_reference",
        "reference_role": "source_binding_reference",
        "is_deployable": False,
        "uses_source_labels": True,
        "uses_latent_information": False,
        "uses_future_information": False,
        "simulator_only_full_map": True,
    },
    "noisy_state_oracle": {
        "route_display_name": "Noisy-state oracle",
        "information_interface": "simulator_proxy_state",
        "analysis_role": "appendix_diagnostic",
        "reference_role": "diagnostic_control",
        "is_deployable": False,
        "uses_source_labels": False,
        "uses_latent_information": False,
        "uses_future_information": False,
        "simulator_only_full_map": True,
    },
    "latent_state_oracle": {
        "route_display_name": "Latent-state oracle",
        "information_interface": "latent_state",
        "analysis_role": "appendix_diagnostic",
        "reference_role": "oracle_reference",
        "is_deployable": False,
        "uses_source_labels": False,
        "uses_latent_information": True,
        "uses_future_information": False,
        "simulator_only_full_map": True,
    },
}

AUDIT_DESIGN_ORDER = [
    "mcar_unweighted",
    "ambiguity_biased_unweighted",
    "ambiguity_biased_ipw",
    "full_population",
]
AUDIT_DESIGN_REGISTRY = {
    "mcar_unweighted": {
        "display_name": "MCAR unweighted",
        "inclusion_mechanism": "mcar",
        "weighting_method": "unweighted",
    },
    "ambiguity_biased_unweighted": {
        "display_name": "Ambiguity-biased unweighted",
        "inclusion_mechanism": "ambiguity_biased",
        "weighting_method": "unweighted",
    },
    "ambiguity_biased_ipw": {
        "display_name": "Ambiguity-biased IPW",
        "inclusion_mechanism": "ambiguity_biased",
        "weighting_method": "inverse_probability",
    },
    "full_population": {
        "display_name": "Full population",
        "inclusion_mechanism": "full_population",
        "weighting_method": "unweighted",
    },
}

CONTROL_ORDER = ["affine_positive", "shuffled_negative", "nonlinear_monotone"]
CONTROL_REGISTRY = {
    "affine_positive": {"display_name": "Affine positive control", "analysis_tier": "primary"},
    "shuffled_negative": {"display_name": "Shuffled negative control", "analysis_tier": "primary"},
    "nonlinear_monotone": {"display_name": "Nonlinear monotone control", "analysis_tier": "appendix"},
}


@dataclass(frozen=True)
class FrozenParameters:
    num_actions: int = 10
    state_dimension: int = 3
    module_a_decision_horizon: int = 5000
    module_a_warmup_rounds: int = 250
    module_b_decision_horizon: int = 2000
    module_b_warmup_rounds: int = 100
    fast_module_a_seeds: int = 3
    full_module_a_seeds: int = 30
    fast_monte_carlo_replications: int = 5
    full_monte_carlo_replications: int = 200
    target_mean_delay: int = 2
    maximum_candidate_delay: int = 20
    delay_state_coupling: float = 2.0
    context_proxy_noise_sd: float = 0.25
    proxy_kernel_bandwidth: float = 0.55
    recency_decay_rate: float = 0.035
    history_ema_rate: float = 0.08
    route_label_rate_primary_audit: float = 0.30
    attribution_proxy_noise_sd_primary_audit: float = 0.25
    audit_temporal_folds: int = 5
    minimum_labelled_units_per_training_split: int = 30
    ambiguity_selection_logit_slope: float = 1.5
    inclusion_probability_lower_bound: float = 0.05
    inclusion_probability_upper_bound: float = 0.95
    inclusion_rate_tolerance: float = 1e-8
    zero_defect_tolerance: float = 1e-12
    raw_defect_epsilon: float = 1e-12
    route_audit_mask_correlation_tolerance: float = 0.05
    bootstrap_replications: int = 2000
    bootstrap_seed: int = 20260724
    confidence_level: float = 0.95
    calibration_control_audit_evidence_rate: float = 0.30
    affine_control_intercept: float = 0.20
    affine_control_slope: float = 1.50
    affine_control_noise_fraction: float = 0.10
    nonlinear_control_scale: float = 1.00


PARAMETERS = FrozenParameters()

MODULE_A_ROUTE_LABEL_RATES = [0.0, 0.3, 0.7, 1.0]
MODULE_A_ATTRIBUTION_PROXY_NOISE_SDS = [0.10, 0.25, 1.00]
AUDIT_EVIDENCE_RATES = [0.1, 0.3, 0.5, 1.0]

PAPER_FIGURE_WIDTH_IN = 7.15
PAPER_FIGURE_HEIGHT_IN = 5.75
PAPER_DPI = 600
AXIS_LABEL_FONT_SIZE = 8.2
TICK_FONT_SIZE = 7.2
LEGEND_FONT_SIZE = 6.8
PANEL_LABEL_FONT_SIZE = 9.0
TITLE_FONT_SIZE = 8.4
LINE_WIDTH = 1.15
MARKER_SIZE = 4.2
CI_ALPHA = 0.18

PRIMARY_FIGURE_STEMS = ["fig_exp4_route_alignment_and_audit"]
APPENDIX_FIGURE_STEMS = [
    "fig_app_exp4_route_boundary_heatmap",
    "fig_app_exp4_alignment_regret_association",
    "fig_app_exp4_four_route_comparison",
    "fig_app_exp4_effective_support",
    "fig_app_exp4_calibration_distributions",
]

REQUIRED_DERIVED_FILES = [
    "exp4_route_boundary_seed_level.parquet",
    "exp4_route_boundary_summary.csv",
    "exp4_route_boundary_pairwise_metrics.parquet",
    "exp4_learner_consequence_appendix.csv",
    "exp4_audit_unit_level.parquet",
    "exp4_raw_estimates.csv",
    "exp4_calibrated_estimates.csv",
    "exp4_calibration_fold_parameters.parquet",
    "exp4_audit_condition_summary.csv",
    "exp4_effective_support_summary.csv",
    "exp4_calibration_control_summary.csv",
    "exp4_population_targets.csv",
]

STREAM_NAMES = [
    "state_stream",
    "structural_feedback_stream",
    "delay_stream",
    "context_proxy_stream",
    "attribution_proxy_stream",
    "route_label_stream",
    "audit_mcar_stream",
    "audit_biased_stream",
    "calibration_noise_stream",
    "shuffle_control_stream",
    "learner_randomization_stream",
    "bootstrap_stream",
]


def route_spec(route_id: str) -> dict[str, Any]:
    if route_id not in ROUTE_REGISTRY:
        raise KeyError(f"Unknown route_id: {route_id}")
    return ROUTE_REGISTRY[route_id]


def audit_design_spec(audit_design_id: str) -> dict[str, str]:
    if audit_design_id not in AUDIT_DESIGN_REGISTRY:
        raise KeyError(f"Unknown audit_design_id: {audit_design_id}")
    return AUDIT_DESIGN_REGISTRY[audit_design_id]


def mode_settings(mode: str) -> dict[str, Any]:
    if mode == "fast":
        return {
            "module_a_seeds": list(range(PARAMETERS.fast_module_a_seeds)),
            "module_a_decision_horizon": PARAMETERS.module_a_decision_horizon,
            "module_a_warmup_rounds": PARAMETERS.module_a_warmup_rounds,
            "module_b_replications": PARAMETERS.fast_monte_carlo_replications,
            "module_b_decision_horizon": 1000,
            "module_b_warmup_rounds": PARAMETERS.module_b_warmup_rounds,
            "bootstrap_replications": 0,
        }
    if mode == "full":
        return {
            "module_a_seeds": list(range(PARAMETERS.full_module_a_seeds)),
            "module_a_decision_horizon": PARAMETERS.module_a_decision_horizon,
            "module_a_warmup_rounds": PARAMETERS.module_a_warmup_rounds,
            "module_b_replications": PARAMETERS.full_monte_carlo_replications,
            "module_b_decision_horizon": PARAMETERS.module_b_decision_horizon,
            "module_b_warmup_rounds": PARAMETERS.module_b_warmup_rounds,
            "bootstrap_replications": PARAMETERS.bootstrap_replications,
        }
    raise ValueError(f"Unknown run mode: {mode}")


def auto_workers(mode: str) -> int:
    cap = 8 if mode == "fast" else 24
    return max(1, min(os.cpu_count() or 1, cap))


def frozen_config_payload() -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment_display_name": EXPERIMENT_DISPLAY_NAME,
        "result_schema": RESULT_SCHEMA,
        "parameters": asdict(PARAMETERS),
        "module_a_route_label_rates": MODULE_A_ROUTE_LABEL_RATES,
        "module_a_attribution_proxy_noise_sds": MODULE_A_ATTRIBUTION_PROXY_NOISE_SDS,
        "audit_evidence_rates": AUDIT_EVIDENCE_RATES,
        "route_registry": ROUTE_REGISTRY,
        "audit_design_registry": AUDIT_DESIGN_REGISTRY,
        "control_registry": CONTROL_REGISTRY,
    }


def config_hash() -> str:
    payload = json.dumps(frozen_config_payload(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def synthetic_input_manifest_hash() -> str:
    payload = "synthetic_controlled_dgp:no_external_input:v1"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

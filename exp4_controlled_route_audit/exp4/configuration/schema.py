"""Result schema, artifact IDs, and v1-to-v2 field migration."""

from __future__ import annotations


EXPERIMENT_ID = "exp4_controlled_route_audit"
EXPERIMENT_DISPLAY_NAME = "Experiment 4: Route Alignment and Evidence-Qualified Audit"
RESULT_SCHEMA = "exp4_controlled_route_audit_v2"
V1_RESULT_SCHEMA = "exp4_controlled_route_audit_v1"
LEGACY_RESULT_SCHEMA = "legacy_exp4_v1"

MODULE_A_ID = "module_a_route_alignment"
MODULE_B_ID = "module_b_audit_reliability"
MODULE_C_ID = "module_c_calibration_controls"

MAIN_FIGURE_ID = "fig_exp4_route_alignment_and_audit_reliability"
MAIN_TABLE_ID = "tbl_exp4_calibration_controls"
APPENDIX_FIGURE_IDS = (
    "fig_app_exp4_module_a_heatmap",
    "fig_app_exp4_paired_contrasts",
    "fig_app_exp4_route_optimal_set_conflict",
    "fig_app_exp4_ambiguity_defect_relation",
    "fig_app_exp4_ipw_weight_diagnostics",
    "fig_app_exp4_effective_support",
    "fig_app_exp4_parameter_recovery",
    "fig_app_exp4_correspondence",
    "fig_app_exp4_attribution_diagnostics",
    "fig_app_exp4_smooth_loss_robustness",
)

FIELD_MIGRATION = {
    "population_raw_action_gap_defect": "population_action_gap_defect",
    "ranking_reversal_rate": "route_optimal_set_conflict_rate",
    "margin_preservation_rate": "margin_certificate_rate",
    "sample_raw_action_gap_defect": "audited_action_gap_defect",
    "raw_estimation_error": "audit_estimation_error",
    "ambiguity_biased_unweighted": "ambiguity_selective_unweighted",
    "ambiguity_biased_ipw": "ambiguity_selective_ipw",
    "shuffled_negative": "blocked_correspondence_destroyed",
    "labelled_support_coefficient": None,
}

REQUIRED_DERIVED_FILES = (
    "derived/module_a/exp4_module_a_seed_level.parquet",
    "derived/module_a/exp4_module_a_population_summary.csv",
    "derived/module_a/exp4_module_a_paired_contrasts.csv",
    "derived/module_a/exp4_module_a_seed_direction_summary.csv",
    "derived/module_b/exp4_module_b_audit_unit_level.parquet",
    "derived/module_b/exp4_module_b_condition_level.parquet",
    "derived/module_b/exp4_module_b_audit_performance.csv",
    "derived/module_b/exp4_module_b_weight_diagnostics.csv",
    "derived/module_b/exp4_module_b_selection_diagnostics.csv",
    "derived/module_c/exp4_module_c_replication_level.parquet",
    "derived/module_c/exp4_module_c_control_summary.csv",
    "derived/module_c/exp4_module_c_parameter_recovery.csv",
    "derived/module_c/exp4_module_c_correspondence_checks.csv",
    "derived/calibration/exp4_proxy_route_calibration.json",
    "derived/calibration/exp4_delay_prior.csv",
    "derived/calibration/exp4_proxy_distance_summary.csv",
)

PRIMARY_MODULE_A_METRICS = (
    "population_action_gap_defect",
    "route_optimal_set_conflict_rate",
    "margin_certificate_rate",
)

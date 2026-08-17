"""Result schema, artifact IDs, v1-to-v2 and v2-to-v3 field migration."""

from __future__ import annotations


EXPERIMENT_ID = "exp4_controlled_route_audit"
EXPERIMENT_DISPLAY_NAME = "Experiment 4: Route Alignment and Evidence-Qualified Audit"
RESULT_SCHEMA = "exp4_controlled_route_audit_v3"
V2_RESULT_SCHEMA = "exp4_controlled_route_audit_v2"
V1_RESULT_SCHEMA = "exp4_controlled_route_audit_v1"
LEGACY_RESULT_SCHEMA = "legacy_exp4_v1"

MODULE_A_ID = "module_a_route_alignment"
MODULE_B_ID = "module_b_audit_reliability"
MODULE_C_ID = "module_c_calibration_controls"

MAIN_FIGURE_ID = "fig_exp4_route_alignment_and_audit_reliability"
MAIN_TABLE_ID = "tbl_exp4_calibration_controls"

# Exact control IDs that appear in the paper main calibration table, in row
# order. Selection is by exact ID (no fuzzy matching); nonlinear_monotone is
# appendix-only.
MAIN_CALIBRATION_CONTROL_IDS = (
    "affine_linked",
    "blocked_correspondence_destroyed",
)
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

# --- v2 -> v3 semantic migration -------------------------------------------------
# The v2 primary scalar ``population_action_gap_defect`` means
# ``mean_round_max_gap_defect`` (the round-max defect averaged over rounds,
# A_T / T). It does NOT migrate by rename to ``mean_pairwise_gap_discrepancy``
# (D_pair). A legacy v2 artifact carrying only the max-based scalar cannot be
# converted to the pair-average primary: the pair-average quantity must be
# recomputed from pair-level / route-map information.
V2_TO_V3_SEMANTIC_MIGRATION = {
    "population_action_gap_defect": {
        "v2_semantic": "mean_round_max_gap_defect",
        "v3_primary_mapping": None,
        "recompute_required_for_v3_primary": True,
        "reason": (
            "v2 population_action_gap_defect is A_T / T (round-max defect); "
            "the v3 primary D_pair (pair-average discrepancy) must be "
            "recomputed from pair-level gap information and cannot be "
            "derived from the max-based scalar."
        ),
    },
}
RECOMPUTE_REQUIRED_FOR_V3_PRIMARY = True


def v3_pairwise_recompute_required(fields: set[str]) -> bool:
    """True when the v3 pair-average primary is absent and cannot be inferred.

    A frame carrying only legacy v2 fields (e.g. ``population_action_gap_defect``)
    must be marked RECOMPUTE_REQUIRED_FOR_V3_PRIMARY rather than silently
    reinterpreted as the pair-average quantity.
    """
    return "mean_pairwise_gap_discrepancy" not in set(fields)

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
    "mean_pairwise_gap_discrepancy",
    "pairwise_gap_sign_disagreement_rate",
    "route_optimal_set_conflict_rate",
)

SECONDARY_MODULE_A_METRICS = (
    "mean_round_max_gap_defect",
    "margin_certificate_rate",
)

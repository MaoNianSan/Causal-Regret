"""Column contracts for the v3 module outputs."""

from __future__ import annotations

import pandas as pd


MODULE_A_COLUMNS = {
    "seed",
    "route_id",
    "route_label_rate",
    "attribution_proxy_noise_sd",
    "mean_pairwise_gap_discrepancy",
    "route_optimal_set_conflict_rate",
    "pairwise_gap_sign_disagreement_rate",
    "mean_round_max_gap_defect",
    "margin_certificate_rate",
    # Legacy v2 field retained for figure/contrast compatibility.
    "population_action_gap_defect",
    "trajectory_hash",
    "route_map_hash",
    "calibration_hash",
    "result_schema",
}
MODULE_B_UNIT_COLUMNS = {
    "replication_id",
    "unit_id",
    "true_unit_mean_pairwise_gap_discrepancy",
    "true_unit_max_gap_defect",
    "ambiguity_score",
    "audit_design_id",
    "audit_evidence_rate",
    "included",
    "inclusion_probability",
    "weight",
    "route_label_indicator",
}
MODULE_B_CONDITION_COLUMNS = {
    "replication_id",
    "audit_design_id",
    "audit_evidence_rate",
    "estimand_id",
    "population_mean_pairwise_gap_discrepancy",
    "audited_mean_pairwise_gap_discrepancy",
    "audit_estimation_error",
    "effective_sample_size",
    "inclusion_mask_hash",
    "estimable",
    "status",
}
MODULE_C_COLUMNS = {
    "replication_id",
    "control_id",
    "raw_pairwise_discrepancy",
    "oof_calibrated_pairwise_discrepancy",
    "recoverability",
    "estimable",
    "status",
}


def has_columns(frame: pd.DataFrame, required: set[str]) -> tuple[bool, str]:
    missing = sorted(required - set(frame.columns))
    return not missing, f"missing={missing}"

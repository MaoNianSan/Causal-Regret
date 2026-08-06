"""Column contracts for the v2 module outputs."""

from __future__ import annotations

import pandas as pd


MODULE_A_COLUMNS = {
    "seed",
    "route_id",
    "route_label_rate",
    "attribution_proxy_noise_sd",
    "population_action_gap_defect",
    "route_optimal_set_conflict_rate",
    "pairwise_gap_sign_disagreement_rate",
    "margin_certificate_rate",
    "trajectory_hash",
    "route_map_hash",
    "calibration_hash",
    "result_schema",
}
MODULE_B_UNIT_COLUMNS = {
    "replication_id",
    "unit_id",
    "true_unit_defect",
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
    "population_action_gap_defect",
    "audited_action_gap_defect",
    "audit_estimation_error",
    "effective_sample_size",
    "inclusion_mask_hash",
    "estimable",
    "status",
}
MODULE_C_COLUMNS = {
    "replication_id",
    "control_id",
    "raw_defect",
    "oof_calibrated_defect",
    "recoverability",
    "estimable",
    "status",
}


def has_columns(frame: pd.DataFrame, required: set[str]) -> tuple[bool, str]:
    missing = sorted(required - set(frame.columns))
    return not missing, f"missing={missing}"

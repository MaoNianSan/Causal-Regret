"""Metric lists and support gate used by bootstrap summaries."""
from __future__ import annotations

import pandas as pd

from config import ExperimentConfig


CANONICAL_ROUTE_METRICS = (
    "pooled_supported_cell_spearman",
    "pooled_supported_cell_mae",
    "exposure_weighted_supported_cell_mae",
    "within_audit_unit_centered_spearman",
    "calibration_intercept",
    "calibration_slope",
    "maximum_heldout_reference_pair_gap_error",
    "mean_absolute_reference_pair_gap_error",
    "p90_absolute_reference_pair_gap_error",
    "heldout_reference_pair_sign_agreement",
    "near_tie_pair_share",
    "signed_cross_fitted_reference_minus_route_value_difference",
    "top_action_agreement_with_fold_reference",
)

ROUTE_METRICS = (
    "score_spearman_correlation",
    "score_calibration_mae",
    "heldout_gap_defect",
    "gap_sign_agreement",
    "gap_reversal_rate",
    "cross_fitted_ranking_shortfall",
    "top_action_match_rate",
)


def support_status(support: pd.DataFrame, cfg: ExperimentConfig) -> str:
    row = support.iloc[0]
    values = [
        float(row.action_coverage),
        float(row.reference_pair_coverage),
        float(row.audit_unit_coverage),
    ]
    if any(value < cfg.support_limited_threshold for value in values):
        return "STOP_AND_REVIEW"
    if any(value < cfg.history_support_pass_threshold for value in values):
        return "PASS_WITH_LIMITED_SUPPORT"
    return "PASS"

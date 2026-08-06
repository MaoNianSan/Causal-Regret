"""Deprecated compatibility exports for v2 audit and calibration APIs."""

from exp4.audit.estimators import (
    EstimateResult,
    NotEstimableError,
    estimate_hajek_ipw_mean,
    estimate_unweighted_mean,
)
from exp4.audit.inclusion import (
    AuditInclusionDesign,
    construct_audit_designs,
    solve_selective_inclusion_probabilities,
)
from exp4.audit.support import compute_effective_sample_size
from exp4.calibration.affine import (
    AffineFitResult,
    fit_weighted_affine_calibration,
    predict_affine_calibration,
)
from exp4.calibration.temporal_folds import construct_contiguous_temporal_folds

__all__ = [
    "AffineFitResult",
    "AuditInclusionDesign",
    "EstimateResult",
    "NotEstimableError",
    "compute_effective_sample_size",
    "construct_audit_designs",
    "construct_contiguous_temporal_folds",
    "estimate_hajek_ipw_mean",
    "estimate_unweighted_mean",
    "fit_weighted_affine_calibration",
    "predict_affine_calibration",
    "solve_selective_inclusion_probabilities",
]

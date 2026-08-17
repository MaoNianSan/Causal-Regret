"""Module B orchestration for finite and selective audit reliability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from exp4.audit.diagnostics import (
    ambiguity_decile_records,
    safe_correlation,
    selection_diagnostics,
)
from exp4.audit.estimators import (
    NotEstimableError,
    estimate_hajek_ipw_mean,
    estimate_unweighted_mean,
)
from exp4.audit.inclusion import construct_audit_designs, standardize_ambiguity
from exp4.audit.support import compute_effective_sample_size, weight_diagnostics
from exp4.configuration.parameters import MODULE_B
from exp4.metrics.action_gaps import GapDiscrepancyResult, compute_gap_discrepancies
from exp4.routes.source_bound import RouteMapResult
from exp4.simulation.trajectory import StructuralTrajectory


@dataclass(frozen=True)
class ModuleBResult:
    unit_level: pd.DataFrame
    condition_records: list[dict[str, Any]]
    ambiguity_decile_records: list[dict[str, Any]]
    discrepancy_result: GapDiscrepancyResult


# The v3 primary audit estimand: mean over unordered supported action pairs of
# absolute route-vs-structural gap discrepancy (d_i_pair).
MODULE_B_ESTIMAND_ID = "mean_pairwise_gap_discrepancy"


def _evaluate_design(
    replication_id: int,
    design,
    discrepancies: GapDiscrepancyResult,
    ambiguity: np.ndarray,
    standardized: np.ndarray,
    diagnostics,
    evaluation: slice,
    route_label_indicator: np.ndarray,
) -> tuple[dict[str, Any], pd.DataFrame]:
    included = design.inclusion_mask
    included_count = int(np.sum(included))
    included_weights = design.weights[included]
    status = "ESTIMABLE"
    # All designs (MCAR unweighted, ambiguity-selective unweighted, and
    # ambiguity-selective Hajek IPW) estimate the SAME pair-average target
    # d_i_pair = round_mean_pairwise_discrepancy.
    unit_pairwise = discrepancies.round_mean_pairwise_discrepancy
    try:
        estimator = (
            estimate_hajek_ipw_mean
            if design.design_id == "ambiguity_selective_ipw"
            else lambda values, weights: estimate_unweighted_mean(values)
        )
        audited_pairwise = estimator(unit_pairwise[included], included_weights).estimate
    except NotEstimableError as exc:
        audited_pairwise = np.nan
        status = f"NOT_ESTIMABLE:{exc}"
    effective_sample_size = compute_effective_sample_size(included_weights)
    population_size = len(unit_pairwise)
    mask_correlation = safe_correlation(route_label_indicator, included)
    population = discrepancies.population_mean_pairwise_discrepancy
    record = {
        "replication_id": int(replication_id),
        "audit_design_id": design.design_id,
        "audit_evidence_rate": design.evidence_rate,
        "estimand_id": MODULE_B_ESTIMAND_ID,
        "population_mean_pairwise_gap_discrepancy": population,
        "audited_mean_pairwise_gap_discrepancy": audited_pairwise,
        "audit_estimation_error": audited_pairwise - population,
        "absolute_audit_error": abs(audited_pairwise - population),
        "labelled_sample_size": included_count,
        "effective_sample_size": effective_sample_size,
        "effective_to_labelled_ratio": (
            effective_sample_size / included_count if included_count else np.nan
        ),
        "effective_to_population_ratio": effective_sample_size / population_size,
        **weight_diagnostics(included_weights, design.inclusion_probabilities),
        **selection_diagnostics(ambiguity, unit_pairwise, included),
        "route_label_audit_mask_correlation": mask_correlation,
        "mean_inclusion_probability": float(np.mean(design.inclusion_probabilities)),
        "minimum_inclusion_probability": float(np.min(design.inclusion_probabilities)),
        "maximum_inclusion_probability": float(np.max(design.inclusion_probabilities)),
        "inclusion_mask_hash": design.mask_hash,
        "inclusion_probability_hash": design.probability_hash,
        "estimable": np.isfinite(audited_pairwise),
        "status": status,
    }
    frame = pd.DataFrame(
        {
            "replication_id": replication_id,
            "unit_id": np.arange(population_size, dtype=np.int64),
            "true_unit_mean_pairwise_gap_discrepancy": unit_pairwise,
            # Secondary legacy robustness field; NOT the v3 primary estimand.
            "true_unit_max_gap_defect": discrepancies.round_max_gap_defect,
            "ambiguity_score": ambiguity,
            "standardized_ambiguity": standardized,
            "candidate_count": diagnostics.contributor_count[evaluation],
            "maximum_assignment_mass": diagnostics.maximum_assignment_mass[evaluation],
            "audit_design_id": design.design_id,
            "audit_evidence_rate": design.evidence_rate,
            "included": included,
            "inclusion_probability": design.inclusion_probabilities,
            "weight": design.weights,
            "route_label_indicator": route_label_indicator,
            "route_label_audit_mask_correlation": mask_correlation,
            "inclusion_mask_hash": design.mask_hash,
        }
    )
    return record, frame


def run_module_b(
    replication_id: int,
    trajectory: StructuralTrajectory,
    proxy_route: RouteMapResult,
) -> ModuleBResult:
    evaluation = trajectory.evaluation_slice
    structural = trajectory.structural_loss_map[evaluation]
    route = proxy_route.route_loss_map[evaluation]
    discrepancies = compute_gap_discrepancies(structural, route)
    diagnostics = proxy_route.diagnostics
    if diagnostics is None:
        raise RuntimeError("Module B requires proxy attribution diagnostics")
    ambiguity = diagnostics.normalized_entropy[evaluation]
    standardized = standardize_ambiguity(ambiguity)
    route_label_indicator = trajectory.route_label_mask(MODULE_B.route_label_rate)[
        evaluation
    ]
    designs = construct_audit_designs(
        ambiguity,
        trajectory.audit_uniform_mcar[evaluation],
        trajectory.audit_uniform_selective[evaluation],
    )
    unit_frames: list[pd.DataFrame] = []
    condition_records: list[dict[str, Any]] = []
    for design in designs:
        condition, unit_frame = _evaluate_design(
            replication_id,
            design,
            discrepancies,
            ambiguity,
            standardized,
            diagnostics,
            evaluation,
            route_label_indicator,
        )
        condition_records.append(condition)
        unit_frames.append(unit_frame)
    deciles = ambiguity_decile_records(
        replication_id, ambiguity, discrepancies.round_mean_pairwise_discrepancy
    )
    return ModuleBResult(
        pd.concat(unit_frames, ignore_index=True),
        condition_records,
        deciles,
        discrepancies,
    )

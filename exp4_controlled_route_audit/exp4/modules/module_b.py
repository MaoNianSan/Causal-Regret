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
from exp4.metrics.action_gaps import ActionGapDefectResult, compute_action_gap_defect
from exp4.routes.source_bound import RouteMapResult
from exp4.simulation.trajectory import StructuralTrajectory


@dataclass(frozen=True)
class ModuleBResult:
    unit_level: pd.DataFrame
    condition_records: list[dict[str, Any]]
    ambiguity_decile_records: list[dict[str, Any]]
    defect_result: ActionGapDefectResult


def _evaluate_design(
    replication_id: int,
    design,
    defect: ActionGapDefectResult,
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
    try:
        estimator = (
            estimate_hajek_ipw_mean
            if design.design_id == "ambiguity_selective_ipw"
            else lambda values, weights: estimate_unweighted_mean(values)
        )
        audited_defect = estimator(
            defect.round_max_gap_defect[included], included_weights
        ).estimate
    except NotEstimableError as exc:
        audited_defect = np.nan
        status = f"NOT_ESTIMABLE:{exc}"
    effective_sample_size = compute_effective_sample_size(included_weights)
    population_size = len(defect.round_max_gap_defect)
    mask_correlation = safe_correlation(route_label_indicator, included)
    record = {
        "replication_id": int(replication_id),
        "audit_design_id": design.design_id,
        "audit_evidence_rate": design.evidence_rate,
        "population_action_gap_defect": defect.population_action_gap_defect,
        "audited_action_gap_defect": audited_defect,
        "audit_estimation_error": audited_defect - defect.population_action_gap_defect,
        "absolute_audit_error": abs(audited_defect - defect.population_action_gap_defect),
        "labelled_sample_size": included_count,
        "effective_sample_size": effective_sample_size,
        "effective_to_labelled_ratio": effective_sample_size / included_count if included_count else np.nan,
        "effective_to_population_ratio": effective_sample_size / population_size,
        **weight_diagnostics(included_weights, design.inclusion_probabilities),
        **selection_diagnostics(ambiguity, defect.round_max_gap_defect, included),
        "route_label_audit_mask_correlation": mask_correlation,
        "mean_inclusion_probability": float(np.mean(design.inclusion_probabilities)),
        "minimum_inclusion_probability": float(np.min(design.inclusion_probabilities)),
        "maximum_inclusion_probability": float(np.max(design.inclusion_probabilities)),
        "inclusion_mask_hash": design.mask_hash,
        "inclusion_probability_hash": design.probability_hash,
        "estimable": np.isfinite(audited_defect),
        "status": status,
    }
    frame = pd.DataFrame(
        {
            "replication_id": replication_id,
            "unit_id": np.arange(population_size, dtype=np.int64),
            "true_unit_defect": defect.round_max_gap_defect,
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
    defect = compute_action_gap_defect(structural, route)
    diagnostics = proxy_route.diagnostics
    if diagnostics is None:
        raise RuntimeError("Module B requires proxy attribution diagnostics")
    ambiguity = diagnostics.normalized_entropy[evaluation]
    standardized = standardize_ambiguity(ambiguity)
    route_label_indicator = trajectory.route_label_mask(MODULE_B.route_label_rate)[evaluation]
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
            defect,
            ambiguity,
            standardized,
            diagnostics,
            evaluation,
            route_label_indicator,
        )
        condition_records.append(condition)
        unit_frames.append(unit_frame)
    deciles = ambiguity_decile_records(
        replication_id, ambiguity, defect.round_max_gap_defect
    )
    return ModuleBResult(
        pd.concat(unit_frames, ignore_index=True),
        condition_records,
        deciles,
        defect,
    )

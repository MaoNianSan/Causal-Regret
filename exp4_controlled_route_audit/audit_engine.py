"""Evidence-qualified audit simulation, IPW, and temporal cross-calibration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

import config
from route_maps import (
    RouteMapResult,
    action_pair_indices,
    compute_action_gap_defect,
    compute_action_gaps,
)
from simulator import StructuralTrajectory


@dataclass(frozen=True)
class AuditCondition:
    audit_evidence_rate: float
    audit_design_id: str
    inclusion_mechanism: str
    weighting_method: str
    inclusion_mask: np.ndarray
    inclusion_probabilities: np.ndarray
    weights: np.ndarray


@dataclass(frozen=True)
class CalibrationEvaluation:
    sample_calibrated_action_gap_defect: float
    population_calibrated_action_gap_defect_conditional_on_fitted_map: float
    estimated_recoverability: float
    population_recoverability_conditional_on_fitted_map: float
    recoverability_error: float
    is_calibration_estimable: bool
    calibration_status: str
    minimum_pair_training_support: int
    fold_parameter_records: list[dict[str, Any]]
    sample_calibrated_unit_defect: np.ndarray | None
    population_calibrated_unit_defect: np.ndarray | None


def construct_temporal_fold_ids(number_of_units: int, number_of_folds: int) -> np.ndarray:
    fold_ids = np.empty(number_of_units, dtype=np.int64)
    for fold_id, indices in enumerate(np.array_split(np.arange(number_of_units), number_of_folds)):
        fold_ids[indices] = fold_id
    if not np.array_equal(np.sort(np.unique(fold_ids)), np.arange(number_of_folds)):
        raise RuntimeError("Temporal folds do not cover the requested fold IDs.")
    return fold_ids


def _expit(values: np.ndarray) -> np.ndarray:
    output = np.empty_like(values, dtype=np.float64)
    positive = values >= 0
    output[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    exp_values = np.exp(values[~positive])
    output[~positive] = exp_values / (1.0 + exp_values)
    return output


def solve_ambiguity_biased_inclusion_probabilities(
    ambiguity_score: np.ndarray,
    audit_evidence_rate: float,
) -> np.ndarray:
    parameters = config.PARAMETERS
    if audit_evidence_rate >= 1.0:
        return np.ones_like(ambiguity_score, dtype=np.float64)
    standard_deviation = float(np.std(ambiguity_score))
    if standard_deviation <= 1e-14:
        standardized = np.zeros_like(ambiguity_score, dtype=np.float64)
    else:
        standardized = (ambiguity_score - float(np.mean(ambiguity_score))) / standard_deviation

    def probabilities(intercept: float) -> np.ndarray:
        raw = _expit(
            intercept + parameters.ambiguity_selection_logit_slope * standardized
        )
        return np.clip(
            raw,
            parameters.inclusion_probability_lower_bound,
            parameters.inclusion_probability_upper_bound,
        )

    lower, upper = -60.0, 60.0
    for _ in range(240):
        midpoint = 0.5 * (lower + upper)
        mean_probability = float(np.mean(probabilities(midpoint)))
        if mean_probability < audit_evidence_rate:
            lower = midpoint
        else:
            upper = midpoint
    inclusion_probabilities = probabilities(0.5 * (lower + upper))
    discrepancy = abs(float(np.mean(inclusion_probabilities)) - audit_evidence_rate)
    if discrepancy >= parameters.inclusion_rate_tolerance:
        raise RuntimeError(
            "Ambiguity-biased inclusion solver failed the frozen rate tolerance: "
            f"target={audit_evidence_rate}, discrepancy={discrepancy:.3e}"
        )
    return inclusion_probabilities


def construct_audit_conditions(
    trajectory: StructuralTrajectory,
    ambiguity_score: np.ndarray,
) -> list[AuditCondition]:
    evaluation = trajectory.evaluation_slice
    mcar_uniform = trajectory.audit_uniform_mcar[evaluation]
    biased_uniform = trajectory.audit_uniform_biased[evaluation]
    conditions: list[AuditCondition] = []
    for audit_evidence_rate in config.AUDIT_EVIDENCE_RATES:
        if audit_evidence_rate >= 1.0:
            full_mask = np.ones(len(ambiguity_score), dtype=bool)
            conditions.append(
                AuditCondition(
                    audit_evidence_rate=1.0,
                    audit_design_id="full_population",
                    inclusion_mechanism="full_population",
                    weighting_method="unweighted",
                    inclusion_mask=full_mask,
                    inclusion_probabilities=np.ones(len(ambiguity_score), dtype=float),
                    weights=np.ones(len(ambiguity_score), dtype=float),
                )
            )
            continue
        mcar_probabilities = np.full(len(ambiguity_score), audit_evidence_rate, dtype=float)
        mcar_mask = mcar_uniform < audit_evidence_rate
        conditions.append(
            AuditCondition(
                audit_evidence_rate=float(audit_evidence_rate),
                audit_design_id="mcar_unweighted",
                inclusion_mechanism="mcar",
                weighting_method="unweighted",
                inclusion_mask=mcar_mask,
                inclusion_probabilities=mcar_probabilities,
                weights=np.ones(len(ambiguity_score), dtype=float),
            )
        )
        biased_probabilities = solve_ambiguity_biased_inclusion_probabilities(
            ambiguity_score, audit_evidence_rate
        )
        biased_mask = biased_uniform < biased_probabilities
        conditions.append(
            AuditCondition(
                audit_evidence_rate=float(audit_evidence_rate),
                audit_design_id="ambiguity_biased_unweighted",
                inclusion_mechanism="ambiguity_biased",
                weighting_method="unweighted",
                inclusion_mask=biased_mask,
                inclusion_probabilities=biased_probabilities,
                weights=np.ones(len(ambiguity_score), dtype=float),
            )
        )
        conditions.append(
            AuditCondition(
                audit_evidence_rate=float(audit_evidence_rate),
                audit_design_id="ambiguity_biased_ipw",
                inclusion_mechanism="ambiguity_biased",
                weighting_method="inverse_probability",
                inclusion_mask=biased_mask,
                inclusion_probabilities=biased_probabilities,
                weights=1.0 / biased_probabilities,
            )
        )
    return conditions


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    if len(values) == 0:
        return np.nan
    denominator = float(np.sum(weights))
    if denominator <= 0.0:
        return np.nan
    return float(np.sum(weights * values) / denominator)


def effective_sample_size(weights: np.ndarray) -> float:
    if len(weights) == 0:
        return 0.0
    denominator = float(np.sum(weights**2))
    if denominator <= 0.0:
        return 0.0
    return float(np.sum(weights) ** 2 / denominator)


def _fit_pairwise_affine(
    route_action_gap: np.ndarray,
    structural_action_gap: np.ndarray,
    training_mask: np.ndarray,
    regression_weights: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, int, float, bool]:
    training_indices = np.flatnonzero(training_mask)
    training_count = len(training_indices)
    if training_count < config.PARAMETERS.minimum_labelled_units_per_training_split:
        pair_count = route_action_gap.shape[1]
        return (
            np.full(pair_count, np.nan),
            np.full(pair_count, np.nan),
            training_count,
            0.0,
            False,
        )
    x = route_action_gap[training_indices]
    y = structural_action_gap[training_indices]
    weights = regression_weights[training_indices].astype(np.float64)
    weight_sum = float(np.sum(weights))
    if weight_sum <= 0.0:
        pair_count = route_action_gap.shape[1]
        return (
            np.full(pair_count, np.nan),
            np.full(pair_count, np.nan),
            training_count,
            weight_sum,
            False,
        )
    x_mean = np.sum(weights[:, None] * x, axis=0) / weight_sum
    y_mean = np.sum(weights[:, None] * y, axis=0) / weight_sum
    centered_x = x - x_mean
    centered_y = y - y_mean
    weighted_variance = np.sum(weights[:, None] * centered_x**2, axis=0)
    weighted_covariance = np.sum(
        weights[:, None] * centered_x * centered_y, axis=0
    )
    if np.any(weighted_variance <= 1e-14):
        pair_count = route_action_gap.shape[1]
        return (
            np.full(pair_count, np.nan),
            np.full(pair_count, np.nan),
            training_count,
            weight_sum,
            False,
        )
    slope = weighted_covariance / weighted_variance
    intercept = y_mean - slope * x_mean
    is_estimable = bool(np.all(np.isfinite(slope)) and np.all(np.isfinite(intercept)))
    return intercept, slope, training_count, weight_sum, is_estimable


def fit_cross_fitted_calibration(
    route_action_gap: np.ndarray,
    structural_action_gap: np.ndarray,
    raw_unit_defect: np.ndarray,
    condition: AuditCondition,
    fold_ids: np.ndarray,
    population_raw_action_gap_defect: float,
    replication_id: int,
    route_id: str,
) -> CalibrationEvaluation:
    pair_low, pair_high = action_pair_indices(config.PARAMETERS.num_actions)
    calibrated_action_gap = np.full_like(route_action_gap, np.nan, dtype=np.float64)
    parameter_records: list[dict[str, Any]] = []
    minimum_support = route_action_gap.shape[0]
    all_estimable = True
    for fold_id in range(config.PARAMETERS.audit_temporal_folds):
        held_out = fold_ids == fold_id
        training_mask = condition.inclusion_mask & ~held_out
        intercept, slope, training_count, weight_sum, is_estimable = _fit_pairwise_affine(
            route_action_gap,
            structural_action_gap,
            training_mask,
            condition.weights,
        )
        minimum_support = min(minimum_support, training_count)
        if not is_estimable:
            all_estimable = False
        else:
            calibrated_action_gap[held_out] = (
                intercept[None, :] + slope[None, :] * route_action_gap[held_out]
            )
        for pair_index, (action_low, action_high) in enumerate(
            zip(pair_low, pair_high, strict=True)
        ):
            parameter_records.append(
                {
                    "replication_id": int(replication_id),
                    "route_id": route_id,
                    "audit_evidence_rate": condition.audit_evidence_rate,
                    "audit_design_id": condition.audit_design_id,
                    "inclusion_mechanism": condition.inclusion_mechanism,
                    "weighting_method": condition.weighting_method,
                    "fold_id": int(fold_id),
                    "action_pair_low": int(action_low),
                    "action_pair_high": int(action_high),
                    "calibration_intercept": (
                        float(intercept[pair_index]) if is_estimable else np.nan
                    ),
                    "calibration_slope": (
                        float(slope[pair_index]) if is_estimable else np.nan
                    ),
                    "training_labelled_units": int(training_count),
                    "training_weight_sum": float(weight_sum),
                    "is_calibration_estimable": bool(is_estimable),
                }
            )
    if not all_estimable:
        return CalibrationEvaluation(
            sample_calibrated_action_gap_defect=np.nan,
            population_calibrated_action_gap_defect_conditional_on_fitted_map=np.nan,
            estimated_recoverability=np.nan,
            population_recoverability_conditional_on_fitted_map=np.nan,
            recoverability_error=np.nan,
            is_calibration_estimable=False,
            calibration_status="NOT_ESTIMABLE",
            minimum_pair_training_support=int(minimum_support),
            fold_parameter_records=parameter_records,
            sample_calibrated_unit_defect=None,
            population_calibrated_unit_defect=None,
        )
    population_calibrated_unit_defect = np.max(
        np.abs(calibrated_action_gap - structural_action_gap), axis=1
    )
    labelled = condition.inclusion_mask
    labelled_weights = condition.weights[labelled]
    sample_calibrated = _weighted_mean(
        population_calibrated_unit_defect[labelled], labelled_weights
    )
    population_calibrated = float(np.mean(population_calibrated_unit_defect))
    sample_raw = _weighted_mean(raw_unit_defect[labelled], labelled_weights)
    if sample_raw > config.PARAMETERS.raw_defect_epsilon:
        estimated_recoverability = 1.0 - sample_calibrated / sample_raw
    else:
        estimated_recoverability = np.nan
    if population_raw_action_gap_defect > config.PARAMETERS.raw_defect_epsilon:
        population_recoverability = (
            1.0 - population_calibrated / population_raw_action_gap_defect
        )
    else:
        population_recoverability = np.nan
    recoverability_error = (
        estimated_recoverability - population_recoverability
        if np.isfinite(estimated_recoverability)
        and np.isfinite(population_recoverability)
        else np.nan
    )
    return CalibrationEvaluation(
        sample_calibrated_action_gap_defect=float(sample_calibrated),
        population_calibrated_action_gap_defect_conditional_on_fitted_map=float(
            population_calibrated
        ),
        estimated_recoverability=float(estimated_recoverability),
        population_recoverability_conditional_on_fitted_map=float(
            population_recoverability
        ),
        recoverability_error=float(recoverability_error),
        is_calibration_estimable=True,
        calibration_status="ESTIMABLE",
        minimum_pair_training_support=int(minimum_support),
        fold_parameter_records=parameter_records,
        sample_calibrated_unit_defect=population_calibrated_unit_defect[labelled],
        population_calibrated_unit_defect=population_calibrated_unit_defect,
    )


def audit_route(
    trajectory: StructuralTrajectory,
    route_result: RouteMapResult,
    ambiguity_score: np.ndarray,
    replication_id: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    evaluation = trajectory.evaluation_slice
    structural_map = trajectory.structural_loss_map[evaluation]
    route_map = route_result.route_loss_map[evaluation]
    structural_action_gap, route_action_gap, raw_unit_defect = compute_action_gap_defect(
        structural_map, route_map
    )
    population_raw_defect = float(np.mean(raw_unit_defect))
    fold_ids = construct_temporal_fold_ids(
        len(raw_unit_defect), config.PARAMETERS.audit_temporal_folds
    )
    raw_records: list[dict[str, Any]] = []
    calibrated_records: list[dict[str, Any]] = []
    parameter_records: list[dict[str, Any]] = []
    for condition in construct_audit_conditions(trajectory, ambiguity_score):
        labelled = condition.inclusion_mask
        labelled_count = int(np.sum(labelled))
        labelled_weights = condition.weights[labelled]
        sample_raw_defect = _weighted_mean(raw_unit_defect[labelled], labelled_weights)
        effective_labelled = effective_sample_size(labelled_weights)
        labelled_support_coefficient = float(
            np.log1p(effective_labelled) / np.log1p(len(raw_unit_defect))
        )
        pair_coverage_rate = 1.0
        raw_records.append(
            {
                "replication_id": int(replication_id),
                "route_id": route_result.route_id,
                "route_label_rate": config.PARAMETERS.route_label_rate_primary_audit,
                "audit_evidence_rate": condition.audit_evidence_rate,
                "audit_design_id": condition.audit_design_id,
                "inclusion_mechanism": condition.inclusion_mechanism,
                "weighting_method": condition.weighting_method,
                "sample_raw_action_gap_defect": sample_raw_defect,
                "population_raw_action_gap_defect": population_raw_defect,
                "raw_estimation_error": sample_raw_defect - population_raw_defect,
                "absolute_raw_estimation_error": abs(
                    sample_raw_defect - population_raw_defect
                ),
                "labelled_audit_sample_size": labelled_count,
                "effective_labelled_sample_size": effective_labelled,
                "labelled_support_coefficient": labelled_support_coefficient,
                "pair_coverage_rate": pair_coverage_rate,
                "mean_inclusion_probability": float(
                    np.mean(condition.inclusion_probabilities)
                ),
                "minimum_inclusion_probability": float(
                    np.min(condition.inclusion_probabilities)
                ),
                "maximum_inclusion_probability": float(
                    np.max(condition.inclusion_probabilities)
                ),
                "route_audit_mask_correlation": _mask_correlation(
                    trajectory.route_label_mask(
                        config.PARAMETERS.route_label_rate_primary_audit
                    )[evaluation],
                    labelled,
                ),
            }
        )
        calibration = fit_cross_fitted_calibration(
            route_action_gap=route_action_gap,
            structural_action_gap=structural_action_gap,
            raw_unit_defect=raw_unit_defect,
            condition=condition,
            fold_ids=fold_ids,
            population_raw_action_gap_defect=population_raw_defect,
            replication_id=replication_id,
            route_id=route_result.route_id,
        )
        parameter_records.extend(calibration.fold_parameter_records)
        calibrated_records.append(
            {
                "replication_id": int(replication_id),
                "route_id": route_result.route_id,
                "route_label_rate": config.PARAMETERS.route_label_rate_primary_audit,
                "audit_evidence_rate": condition.audit_evidence_rate,
                "audit_design_id": condition.audit_design_id,
                "inclusion_mechanism": condition.inclusion_mechanism,
                "weighting_method": condition.weighting_method,
                "sample_calibrated_action_gap_defect": calibration.sample_calibrated_action_gap_defect,
                "population_calibrated_action_gap_defect_conditional_on_fitted_map": calibration.population_calibrated_action_gap_defect_conditional_on_fitted_map,
                "calibrated_estimation_error": (
                    calibration.sample_calibrated_action_gap_defect
                    - calibration.population_calibrated_action_gap_defect_conditional_on_fitted_map
                    if calibration.is_calibration_estimable
                    else np.nan
                ),
                "estimated_recoverability": calibration.estimated_recoverability,
                "population_recoverability_conditional_on_fitted_map": calibration.population_recoverability_conditional_on_fitted_map,
                "recoverability_error": calibration.recoverability_error,
                "absolute_recoverability_error": (
                    abs(calibration.recoverability_error)
                    if np.isfinite(calibration.recoverability_error)
                    else np.nan
                ),
                "is_calibration_estimable": calibration.is_calibration_estimable,
                "calibration_status": calibration.calibration_status,
                "minimum_pair_training_support": calibration.minimum_pair_training_support,
            }
        )
    return raw_records, calibrated_records, parameter_records


def construct_audit_unit_records(
    trajectory: StructuralTrajectory,
    route_results: dict[str, RouteMapResult],
    ambiguity_score: np.ndarray,
    contributor_count: np.ndarray,
    maximum_assignment_mass: np.ndarray,
    replication_id: int,
) -> list[dict[str, Any]]:
    evaluation_rounds = np.arange(
        trajectory.warmup_rounds, trajectory.decision_horizon, dtype=int
    )
    route_label_mask = trajectory.route_label_mask(
        config.PARAMETERS.route_label_rate_primary_audit
    )
    records: list[dict[str, Any]] = []
    for route_id in config.ROUTE_ORDER:
        route_result = route_results[route_id]
        _, _, raw_unit_defect = compute_action_gap_defect(
            trajectory.structural_loss_map[trajectory.evaluation_slice],
            route_result.route_loss_map[trajectory.evaluation_slice],
        )
        for position, audit_round in enumerate(evaluation_rounds):
            records.append(
                {
                    "replication_id": int(replication_id),
                    "audit_round": int(audit_round),
                    "route_id": route_id,
                    "raw_unit_action_gap_defect": float(raw_unit_defect[position]),
                    "base_ambiguity_score": float(ambiguity_score[position]),
                    "candidate_contributor_count": int(contributor_count[position]),
                    "maximum_assignment_mass": float(
                        maximum_assignment_mass[position]
                    ),
                    "is_source_label_observed": bool(route_label_mask[audit_round]),
                    "audit_uniform_mcar": float(
                        trajectory.audit_uniform_mcar[audit_round]
                    ),
                    "audit_uniform_biased": float(
                        trajectory.audit_uniform_biased[audit_round]
                    ),
                    "structural_map_hash": trajectory.path_hashes[
                        "structural_loss_map_hash"
                    ],
                    "route_map_hash": route_result.route_map_hash,
                }
            )
    return records


def construct_population_target_records(
    trajectory: StructuralTrajectory,
    route_results: dict[str, RouteMapResult],
    replication_id: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for route_id in config.ROUTE_ORDER:
        _, _, raw_unit_defect = compute_action_gap_defect(
            trajectory.structural_loss_map[trajectory.evaluation_slice],
            route_results[route_id].route_loss_map[trajectory.evaluation_slice],
        )
        records.append(
            {
                "replication_id": int(replication_id),
                "route_id": route_id,
                "population_raw_action_gap_defect": float(np.mean(raw_unit_defect)),
                "pair_coverage_rate": 1.0,
                "structural_map_hash": trajectory.path_hashes[
                    "structural_loss_map_hash"
                ],
                "route_map_hash": route_results[route_id].route_map_hash,
            }
        )
    return records


def _mask_correlation(first: np.ndarray, second: np.ndarray) -> float:
    first_float = first.astype(float)
    second_float = second.astype(float)
    if float(np.std(first_float)) <= 1e-14 or float(np.std(second_float)) <= 1e-14:
        return np.nan
    return float(np.corrcoef(first_float, second_float)[0, 1])


def _independent_affine_control_scale() -> float:
    generator = np.random.default_rng(np.random.SeedSequence(2026072401))
    calibration_generation_sample = generator.normal(size=100_000)
    reference = (
        config.PARAMETERS.affine_control_intercept
        + config.PARAMETERS.affine_control_slope * calibration_generation_sample
    )
    return float(np.std(reference))


AFFINE_CONTROL_REFERENCE_SCALE = _independent_affine_control_scale()


def construct_calibration_control_signals(
    control_id: str,
    base_route_action_gap: np.ndarray,
    base_structural_action_gap: np.ndarray,
    fold_ids: np.ndarray,
    replication_id: int,
) -> tuple[np.ndarray, np.ndarray]:
    if control_id == "affine_positive":
        generator = np.random.default_rng(
            np.random.SeedSequence([replication_id, 821, 1])
        )
        noise = generator.normal(
            0.0,
            config.PARAMETERS.affine_control_noise_fraction
            * AFFINE_CONTROL_REFERENCE_SCALE,
            size=base_route_action_gap.shape,
        )
        q_signal = base_route_action_gap.copy()
        phi_signal = (
            config.PARAMETERS.affine_control_intercept
            + config.PARAMETERS.affine_control_slope * q_signal
            + noise
        )
        return q_signal, phi_signal
    if control_id == "shuffled_negative":
        generator = np.random.default_rng(
            np.random.SeedSequence([replication_id, 821, 2])
        )
        q_signal = base_route_action_gap.copy()
        for fold_id in range(config.PARAMETERS.audit_temporal_folds):
            fold_positions = np.flatnonzero(fold_ids == fold_id)
            for pair_index in range(q_signal.shape[1]):
                permutation = generator.permutation(fold_positions)
                q_signal[fold_positions, pair_index] = base_route_action_gap[
                    permutation, pair_index
                ]
        return q_signal, base_structural_action_gap.copy()
    if control_id == "nonlinear_monotone":
        generator = np.random.default_rng(
            np.random.SeedSequence([replication_id, 821, 3])
        )
        q_signal = base_route_action_gap.copy()
        noise = generator.normal(
            0.0,
            config.PARAMETERS.affine_control_noise_fraction
            * AFFINE_CONTROL_REFERENCE_SCALE,
            size=q_signal.shape,
        )
        phi_signal = np.tanh(
            config.PARAMETERS.nonlinear_control_scale * q_signal
        ) + noise
        return q_signal, phi_signal
    raise KeyError(f"Unknown control_id: {control_id}")


def evaluate_calibration_controls(
    trajectory: StructuralTrajectory,
    proxy_route_result: RouteMapResult,
    replication_id: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evaluation = trajectory.evaluation_slice
    base_route_action_gap = compute_action_gaps(
        proxy_route_result.route_loss_map[evaluation]
    )
    base_structural_action_gap = compute_action_gaps(
        trajectory.structural_loss_map[evaluation]
    )
    number_of_units = base_route_action_gap.shape[0]
    fold_ids = construct_temporal_fold_ids(
        number_of_units, config.PARAMETERS.audit_temporal_folds
    )
    rho = config.PARAMETERS.calibration_control_audit_evidence_rate
    inclusion_mask = (
        trajectory.audit_uniform_mcar[evaluation] < rho
    )
    condition = AuditCondition(
        audit_evidence_rate=rho,
        audit_design_id="mcar_unweighted",
        inclusion_mechanism="mcar",
        weighting_method="unweighted",
        inclusion_mask=inclusion_mask,
        inclusion_probabilities=np.full(number_of_units, rho),
        weights=np.ones(number_of_units),
    )
    control_records: list[dict[str, Any]] = []
    parameter_records: list[dict[str, Any]] = []
    for control_id in config.CONTROL_ORDER:
        q_signal, phi_signal = construct_calibration_control_signals(
            control_id,
            base_route_action_gap,
            base_structural_action_gap,
            fold_ids,
            replication_id,
        )
        raw_unit_defect = np.max(np.abs(q_signal - phi_signal), axis=1)
        population_raw = float(np.mean(raw_unit_defect))
        labelled = condition.inclusion_mask
        sample_raw = float(np.mean(raw_unit_defect[labelled]))
        calibration = fit_cross_fitted_calibration(
            route_action_gap=q_signal,
            structural_action_gap=phi_signal,
            raw_unit_defect=raw_unit_defect,
            condition=condition,
            fold_ids=fold_ids,
            population_raw_action_gap_defect=population_raw,
            replication_id=replication_id,
            route_id=f"control__{control_id}",
        )
        parameter_records.extend(calibration.fold_parameter_records)
        control_records.append(
            {
                "replication_id": int(replication_id),
                "control_id": control_id,
                "control_display_name": config.CONTROL_REGISTRY[control_id][
                    "display_name"
                ],
                "analysis_tier": config.CONTROL_REGISTRY[control_id][
                    "analysis_tier"
                ],
                "audit_evidence_rate": rho,
                "sample_raw_action_gap_defect": sample_raw,
                "population_raw_action_gap_defect": population_raw,
                "sample_calibrated_action_gap_defect": calibration.sample_calibrated_action_gap_defect,
                "population_calibrated_action_gap_defect_conditional_on_fitted_map": calibration.population_calibrated_action_gap_defect_conditional_on_fitted_map,
                "estimated_recoverability": calibration.estimated_recoverability,
                "population_recoverability_conditional_on_fitted_map": calibration.population_recoverability_conditional_on_fitted_map,
                "negative_recoverability_indicator": (
                    bool(calibration.estimated_recoverability < 0.0)
                    if np.isfinite(calibration.estimated_recoverability)
                    else False
                ),
                "is_calibration_estimable": calibration.is_calibration_estimable,
                "minimum_pair_training_support": calibration.minimum_pair_training_support,
            }
        )
    return control_records, parameter_records


def calibration_parameter_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame.from_records(records)

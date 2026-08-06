"""Module A orchestration for the controlled route-alignment boundary."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from exp4.configuration.parameters import MODULE_A
from exp4.configuration.schema import RESULT_SCHEMA
from exp4.metrics.action_gaps import compute_action_gap_defect
from exp4.metrics.ranking_diagnostics import (
    compute_margin_certificate_rate,
    compute_pairwise_gap_sign_disagreement_rate,
    compute_route_optimal_set_conflict_rate,
)
from exp4.routes.partial_label_proxy import construct_partial_label_proxy_route
from exp4.routes.source_bound import RouteMapResult, construct_source_bound_route
from exp4.simulation.calibration import ProxyRouteCalibration
from exp4.simulation.structural_loss import compute_smooth_robustness_loss_map
from exp4.simulation.trajectory import (
    StructuralTrajectory,
    generate_structural_trajectory,
    hash_array,
)


@dataclass(frozen=True)
class ModuleASeedResult:
    trajectory: StructuralTrajectory
    seed_records: list[dict[str, Any]]


def _evaluate_route(
    trajectory: StructuralTrajectory,
    route_result: RouteMapResult,
    seed: int,
    route_label_rate: float,
    proxy_noise_sd: float,
    calibration_hash: str,
    dgp_id: str = "parity_floor_primary",
) -> dict[str, Any]:
    evaluation = trajectory.evaluation_slice
    structural = trajectory.structural_loss_map[evaluation]
    route = route_result.route_loss_map[evaluation]
    defect = compute_action_gap_defect(structural, route)
    diagnostics = route_result.diagnostics
    return {
        "seed": int(seed),
        "dgp_id": dgp_id,
        "route_id": route_result.route_id,
        "route_label_rate": float(route_label_rate),
        "attribution_proxy_noise_sd": float(proxy_noise_sd),
        "population_action_gap_defect": defect.population_action_gap_defect,
        "route_optimal_set_conflict_rate": compute_route_optimal_set_conflict_rate(
            structural, route
        ),
        "pairwise_gap_sign_disagreement_rate": compute_pairwise_gap_sign_disagreement_rate(
            structural, route
        ),
        "margin_certificate_rate": compute_margin_certificate_rate(
            structural, defect.round_max_gap_defect
        ),
        "mean_attribution_entropy": (
            float(np.mean(diagnostics.normalized_entropy[evaluation]))
            if diagnostics is not None
            else 0.0
        ),
        "mean_candidate_count": (
            float(np.mean(diagnostics.contributor_count[evaluation]))
            if diagnostics is not None
            else 1.0
        ),
        "mean_max_assignment_mass": (
            float(np.nanmean(diagnostics.maximum_assignment_mass[evaluation]))
            if diagnostics is not None
            else 1.0
        ),
        "mean_attribution_mass": (
            float(np.mean(diagnostics.attribution_mass[evaluation]))
            if diagnostics is not None
            else 1.0
        ),
        "mean_true_source_assigned_mass_appendix": (
            float(np.mean(diagnostics.true_source_assigned_mass[evaluation]))
            if diagnostics is not None
            else 1.0
        ),
        "top1_source_recovery_rate_appendix": (
            float(np.mean(diagnostics.top1_source_recovered[evaluation]))
            if diagnostics is not None
            else 1.0
        ),
        "candidate_set_contains_true_source_rate": (
            float(np.mean(diagnostics.candidate_set_contains_true_source[evaluation]))
            if diagnostics is not None
            else 1.0
        ),
        "minimum_attribution_mass": (
            float(np.min(diagnostics.attribution_mass[evaluation]))
            if diagnostics is not None
            else 1.0
        ),
        "finite_weight_checks_pass": (
            bool(diagnostics.finite_weight_checks_pass)
            if diagnostics is not None
            else True
        ),
        "trajectory_hash": trajectory.trajectory_hash,
        "structural_map_hash": hash_array(trajectory.structural_loss_map),
        "route_map_hash": route_result.route_map_hash,
        "calibration_hash": calibration_hash,
        "schema_version": RESULT_SCHEMA,
    }


def run_module_a_seed(
    seed: int, calibration: ProxyRouteCalibration
) -> ModuleASeedResult:
    trajectory = generate_structural_trajectory(
        "module_a", seed, MODULE_A.horizon, MODULE_A.warmup
    )
    records: list[dict[str, Any]] = []
    source_bound = construct_source_bound_route(trajectory)
    records.append(
        _evaluate_route(
            trajectory,
            source_bound,
            seed,
            1.0,
            MODULE_A.primary_proxy_noise_sd,
            calibration.calibration_hash,
        )
    )
    for proxy_noise_sd in MODULE_A.proxy_noise_sds:
        for route_label_rate in MODULE_A.route_label_rates:
            route = construct_partial_label_proxy_route(
                trajectory,
                route_label_rate,
                proxy_noise_sd,
                calibration,
            )
            records.append(
                _evaluate_route(
                    trajectory,
                    route,
                    seed,
                    route_label_rate,
                    proxy_noise_sd,
                    calibration.calibration_hash,
                )
            )
    smooth_trajectory = replace(
        trajectory,
        structural_loss_map=compute_smooth_robustness_loss_map(
            trajectory.structural_states, trajectory.action_centers
        ),
    )
    for route_label_rate in MODULE_A.route_label_rates:
        route = construct_partial_label_proxy_route(
            smooth_trajectory,
            route_label_rate,
            MODULE_A.primary_proxy_noise_sd,
            calibration,
        )
        route = RouteMapResult(
            "proxy_label_smooth_robustness",
            route.route_loss_map,
            route.route_map_hash,
            route.diagnostics,
        )
        records.append(
            _evaluate_route(
                smooth_trajectory,
                route,
                seed,
                route_label_rate,
                MODULE_A.primary_proxy_noise_sd,
                calibration.calibration_hash,
                dgp_id="smooth_no_parity_floor",
            )
        )
    return ModuleASeedResult(trajectory, records)

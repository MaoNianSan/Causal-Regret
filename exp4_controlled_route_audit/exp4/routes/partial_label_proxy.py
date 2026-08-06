"""Partial-label route using arrival-side source signatures and a frozen delay prior."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from exp4.configuration.parameters import SHARED_DGP
from exp4.routes.common import candidate_sources, compute_candidate_weights
from exp4.routes.source_bound import RouteMapResult
from exp4.simulation.calibration import ProxyRouteCalibration
from exp4.simulation.trajectory import StructuralTrajectory, hash_array


@dataclass(frozen=True)
class AttributionDiagnostics:
    attribution_mass: np.ndarray
    normalized_entropy: np.ndarray
    contributor_count: np.ndarray
    maximum_assignment_mass: np.ndarray
    true_source_assigned_mass: np.ndarray
    top1_source_recovered: np.ndarray
    candidate_set_contains_true_source: np.ndarray
    no_mass_count: int
    finite_weight_checks_pass: bool


def _label_blind_assignments(
    trajectory: StructuralTrajectory,
    proxy_noise_sd: float,
    calibration: ProxyRouteCalibration,
) -> tuple[list[tuple[np.ndarray, np.ndarray]], AttributionDiagnostics]:
    signatures = trajectory.observation_proxy.arrival_signature(proxy_noise_sd)
    incoming: list[list[float]] = [[] for _ in range(trajectory.decision_horizon)]
    assignments: list[tuple[np.ndarray, np.ndarray]] = []
    true_mass = np.zeros(trajectory.decision_horizon, dtype=np.float64)
    top1 = np.zeros(trajectory.decision_horizon, dtype=bool)
    contains_true = np.zeros(trajectory.decision_horizon, dtype=bool)
    finite_pass = True
    for source_round, arrival_clock in enumerate(trajectory.arrival_clocks):
        candidates = candidate_sources(
            int(arrival_clock),
            trajectory.decision_horizon,
            SHARED_DGP.maximum_candidate_delay,
        )
        delays = int(arrival_clock) - candidates
        weights = compute_candidate_weights(
            trajectory.observation_proxy.source_proxy[candidates],
            signatures[source_round],
            delays,
            calibration.kernel_bandwidth,
            calibration.delay_probabilities,
        )
        assignments.append((candidates, weights))
        finite_pass = finite_pass and bool(np.all(np.isfinite(weights)))
        true_positions = np.flatnonzero(candidates == source_round)
        contains_true[source_round] = true_positions.size == 1
        if true_positions.size == 1:
            true_mass[source_round] = float(weights[int(true_positions[0])])
            top1[source_round] = int(candidates[int(np.argmax(weights))]) == source_round
        for candidate, weight in zip(candidates, weights, strict=True):
            incoming[int(candidate)].append(float(weight))
    attribution_mass = np.zeros(trajectory.decision_horizon, dtype=np.float64)
    entropy = np.zeros(trajectory.decision_horizon, dtype=np.float64)
    count = np.zeros(trajectory.decision_horizon, dtype=np.int64)
    maximum = np.full(trajectory.decision_horizon, np.nan, dtype=np.float64)
    for unit_id, values in enumerate(incoming):
        if not values:
            continue
        incoming_weights = np.asarray(values, dtype=np.float64)
        attribution_mass[unit_id] = float(np.sum(incoming_weights))
        normalized = incoming_weights / attribution_mass[unit_id]
        count[unit_id] = len(normalized)
        maximum[unit_id] = float(np.max(normalized))
        if len(normalized) > 1:
            entropy[unit_id] = float(
                -np.sum(normalized * np.log(np.maximum(normalized, 1e-300)))
                / np.log(len(normalized))
            )
    diagnostics = AttributionDiagnostics(
        attribution_mass=attribution_mass,
        normalized_entropy=entropy,
        contributor_count=count,
        maximum_assignment_mass=maximum,
        true_source_assigned_mass=true_mass,
        top1_source_recovered=top1,
        candidate_set_contains_true_source=contains_true,
        no_mass_count=int(np.sum(attribution_mass <= 0.0)),
        finite_weight_checks_pass=finite_pass,
    )
    return assignments, diagnostics


def construct_partial_label_proxy_route(
    trajectory: StructuralTrajectory,
    route_label_rate: float,
    proxy_noise_sd: float,
    calibration: ProxyRouteCalibration,
) -> RouteMapResult:
    assignments, label_blind = _label_blind_assignments(
        trajectory, proxy_noise_sd, calibration
    )
    label_mask = trajectory.route_label_mask(route_label_rate)
    numerator = np.zeros_like(trajectory.structural_loss_map)
    attribution_mass = np.zeros(trajectory.decision_horizon, dtype=np.float64)
    for source_round, (candidates, weights) in enumerate(assignments):
        source_map = trajectory.structural_loss_map[source_round]
        if bool(label_mask[source_round]):
            numerator[source_round] += source_map
            attribution_mass[source_round] += 1.0
        else:
            numerator[candidates] += weights[:, None] * source_map[None, :]
            attribution_mass[candidates] += weights
    if np.any(attribution_mass <= 0.0):
        failing = np.flatnonzero(attribution_mass <= 0.0)
        raise RuntimeError(f"Proxy route has zero attribution mass: {failing[:10].tolist()}")
    route_map = numerator / attribution_mass[:, None]
    diagnostics = AttributionDiagnostics(
        attribution_mass=attribution_mass,
        normalized_entropy=label_blind.normalized_entropy,
        contributor_count=label_blind.contributor_count,
        maximum_assignment_mass=label_blind.maximum_assignment_mass,
        true_source_assigned_mass=label_blind.true_source_assigned_mass,
        top1_source_recovered=label_blind.top1_source_recovered,
        candidate_set_contains_true_source=label_blind.candidate_set_contains_true_source,
        no_mass_count=int(np.sum(attribution_mass <= 0.0)),
        finite_weight_checks_pass=label_blind.finite_weight_checks_pass,
    )
    return RouteMapResult("proxy_label", route_map, hash_array(route_map), diagnostics)

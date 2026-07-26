"""Simulator-only full-map operational routes and action-gap diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

import config
from simulator import StructuralTrajectory, hash_array


@dataclass(frozen=True)
class AttributionDiagnostics:
    attribution_mass: np.ndarray
    base_ambiguity_score: np.ndarray
    candidate_contributor_count: np.ndarray
    maximum_assignment_mass: np.ndarray


@dataclass(frozen=True)
class RouteMapResult:
    route_id: str
    route_loss_map: np.ndarray
    route_map_hash: str
    attribution_diagnostics: AttributionDiagnostics | None = None


def action_pair_indices(num_actions: int) -> tuple[np.ndarray, np.ndarray]:
    low, high = np.triu_indices(int(num_actions), k=1)
    return low.astype(np.int64), high.astype(np.int64)


def compute_action_gaps(loss_map: np.ndarray) -> np.ndarray:
    action_pair_low, action_pair_high = action_pair_indices(loss_map.shape[1])
    return loss_map[:, action_pair_low] - loss_map[:, action_pair_high]


def compute_action_gap_defect(
    structural_loss_map: np.ndarray, route_loss_map: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if structural_loss_map.shape != route_loss_map.shape:
        raise ValueError("structural_loss_map and route_loss_map shapes must match")
    structural_action_gap = compute_action_gaps(structural_loss_map)
    route_action_gap = compute_action_gaps(route_loss_map)
    round_action_gap_defect = np.max(
        np.abs(route_action_gap - structural_action_gap), axis=1
    )
    return structural_action_gap, route_action_gap, round_action_gap_defect


def _soft_candidate_weights(
    arrival_clock: int,
    attribution_proxy: np.ndarray,
    decision_horizon: int,
) -> tuple[np.ndarray, np.ndarray]:
    parameters = config.PARAMETERS
    lower = max(0, int(arrival_clock) - parameters.maximum_candidate_delay)
    upper = min(int(arrival_clock), int(decision_horizon))
    candidates = np.arange(lower, upper, dtype=np.int64)
    if len(candidates) == 0:
        raise RuntimeError(
            f"No feasible historical source candidates at arrival_clock={arrival_clock}."
        )
    proxy_difference = attribution_proxy[candidates] - attribution_proxy[int(arrival_clock)]
    squared_distance = np.einsum(
        "ij,ij->i", proxy_difference, proxy_difference, optimize=True
    )
    recency = int(arrival_clock) - candidates
    log_weight = (
        -squared_distance / (2.0 * parameters.proxy_kernel_bandwidth**2)
        - parameters.recency_decay_rate * recency
    )
    log_weight -= float(np.max(log_weight))
    weights = np.exp(log_weight)
    weight_sum = float(weights.sum())
    if not np.isfinite(weight_sum) or weight_sum <= 0.0:
        raise RuntimeError("Proxy attribution weights are non-finite or have zero mass.")
    weights /= weight_sum
    return candidates, weights.astype(np.float64)


def construct_source_bound_route(
    trajectory: StructuralTrajectory,
) -> RouteMapResult:
    route_loss_map = trajectory.structural_loss_map.copy()
    return RouteMapResult(
        route_id="source_bound",
        route_loss_map=route_loss_map,
        route_map_hash=hash_array(route_loss_map),
    )


def construct_arrival_time_route(
    trajectory: StructuralTrajectory,
) -> RouteMapResult:
    number_of_actions = trajectory.structural_loss_map.shape[1]
    route_loss_map = np.empty_like(trajectory.structural_loss_map)
    carried_map = np.full(number_of_actions, 0.5, dtype=np.float64)
    for decision_clock in range(trajectory.decision_horizon):
        arriving_sources = trajectory.arrivals_by_clock[decision_clock]
        if arriving_sources:
            carried_map = np.mean(
                trajectory.structural_loss_map[np.asarray(arriving_sources, dtype=int)],
                axis=0,
            )
        route_loss_map[decision_clock] = carried_map
    return RouteMapResult(
        route_id="arrival_time",
        route_loss_map=route_loss_map,
        route_map_hash=hash_array(route_loss_map),
    )


def construct_history_surrogate_route(
    trajectory: StructuralTrajectory,
) -> RouteMapResult:
    number_of_actions = trajectory.structural_loss_map.shape[1]
    context_ids = trajectory.context_ids()
    history_maps = np.full(
        (number_of_actions, number_of_actions), 0.5, dtype=np.float64
    )
    route_loss_map = np.empty_like(trajectory.structural_loss_map)
    for clock in range(trajectory.clock_horizon):
        arriving_sources = trajectory.arrivals_by_clock[clock]
        current_context = int(context_ids[clock])
        if arriving_sources:
            arrival_batch_map = np.mean(
                trajectory.structural_loss_map[np.asarray(arriving_sources, dtype=int)],
                axis=0,
            )
            history_maps[current_context] = (
                (1.0 - config.PARAMETERS.history_ema_rate)
                * history_maps[current_context]
                + config.PARAMETERS.history_ema_rate * arrival_batch_map
            )
        if clock < trajectory.decision_horizon:
            route_loss_map[clock] = history_maps[current_context]
    return RouteMapResult(
        route_id="history_surrogate",
        route_loss_map=route_loss_map,
        route_map_hash=hash_array(route_loss_map),
    )


def construct_label_blind_attribution_diagnostics(
    trajectory: StructuralTrajectory,
    attribution_proxy_noise_sd: float,
) -> AttributionDiagnostics:
    attribution_proxy = trajectory.attribution_proxy(attribution_proxy_noise_sd)
    incoming_weights: list[list[float]] = [
        [] for _ in range(trajectory.decision_horizon)
    ]
    attribution_mass = np.zeros(trajectory.decision_horizon, dtype=np.float64)
    for source_round, arrival_clock in enumerate(trajectory.arrival_clocks):
        del source_round  # source identity is not used by the label-blind assignment rule
        candidates, weights = _soft_candidate_weights(
            int(arrival_clock), attribution_proxy, trajectory.decision_horizon
        )
        attribution_mass[candidates] += weights
        for candidate, weight in zip(candidates, weights, strict=True):
            incoming_weights[int(candidate)].append(float(weight))
    ambiguity_score = np.zeros(trajectory.decision_horizon, dtype=np.float64)
    contributor_count = np.zeros(trajectory.decision_horizon, dtype=np.int64)
    maximum_assignment_mass = np.ones(trajectory.decision_horizon, dtype=np.float64)
    for audit_round, values in enumerate(incoming_weights):
        count = len(values)
        contributor_count[audit_round] = count
        if count == 0:
            maximum_assignment_mass[audit_round] = np.nan
            continue
        normalized = np.asarray(values, dtype=np.float64)
        normalized /= float(normalized.sum())
        maximum_assignment_mass[audit_round] = float(np.max(normalized))
        if count > 1:
            entropy = -float(np.sum(normalized * np.log(np.maximum(normalized, 1e-300))))
            ambiguity_score[audit_round] = entropy / float(np.log(count))
    return AttributionDiagnostics(
        attribution_mass=attribution_mass,
        base_ambiguity_score=ambiguity_score,
        candidate_contributor_count=contributor_count,
        maximum_assignment_mass=maximum_assignment_mass,
    )


def construct_proxy_label_route(
    trajectory: StructuralTrajectory,
    route_label_rate: float,
    attribution_proxy_noise_sd: float,
    label_blind_diagnostics: AttributionDiagnostics | None = None,
) -> RouteMapResult:
    attribution_proxy = trajectory.attribution_proxy(attribution_proxy_noise_sd)
    route_label_mask = trajectory.route_label_mask(route_label_rate)
    numerator = np.zeros_like(trajectory.structural_loss_map)
    attribution_mass = np.zeros(trajectory.decision_horizon, dtype=np.float64)
    for source_round, arrival_clock in enumerate(trajectory.arrival_clocks):
        source_map = trajectory.structural_loss_map[source_round]
        if bool(route_label_mask[source_round]):
            numerator[source_round] += source_map
            attribution_mass[source_round] += 1.0
            continue
        candidates, weights = _soft_candidate_weights(
            int(arrival_clock), attribution_proxy, trajectory.decision_horizon
        )
        numerator[candidates] += weights[:, None] * source_map[None, :]
        attribution_mass[candidates] += weights
    if np.any(attribution_mass[trajectory.evaluation_slice] <= 0.0):
        failing = np.flatnonzero(
            attribution_mass[trajectory.evaluation_slice] <= 0.0
        ) + trajectory.warmup_rounds
        raise RuntimeError(
            "Proxy-label attribution has zero mass on post-warmup rounds: "
            f"{failing[:10].tolist()}"
        )
    if np.any(attribution_mass <= 0.0):
        failing = np.flatnonzero(attribution_mass <= 0.0)
        raise RuntimeError(
            "Proxy-label route requires positive attribution mass for every structural "
            f"round; failures={failing[:10].tolist()}"
        )
    route_loss_map = numerator / attribution_mass[:, None]
    if label_blind_diagnostics is None:
        label_blind_diagnostics = construct_label_blind_attribution_diagnostics(
            trajectory, attribution_proxy_noise_sd
        )
    diagnostics = AttributionDiagnostics(
        attribution_mass=attribution_mass,
        base_ambiguity_score=label_blind_diagnostics.base_ambiguity_score,
        candidate_contributor_count=label_blind_diagnostics.candidate_contributor_count,
        maximum_assignment_mass=label_blind_diagnostics.maximum_assignment_mass,
    )
    return RouteMapResult(
        route_id="proxy_label",
        route_loss_map=route_loss_map,
        route_map_hash=hash_array(route_loss_map),
        attribution_diagnostics=diagnostics,
    )


def construct_all_route_maps(
    trajectory: StructuralTrajectory,
    route_label_rate: float,
    attribution_proxy_noise_sd: float,
) -> dict[str, RouteMapResult]:
    label_blind_diagnostics = construct_label_blind_attribution_diagnostics(
        trajectory, attribution_proxy_noise_sd
    )
    results = {
        "arrival_time": construct_arrival_time_route(trajectory),
        "history_surrogate": construct_history_surrogate_route(trajectory),
        "proxy_label": construct_proxy_label_route(
            trajectory,
            route_label_rate=route_label_rate,
            attribution_proxy_noise_sd=attribution_proxy_noise_sd,
            label_blind_diagnostics=label_blind_diagnostics,
        ),
        "source_bound": construct_source_bound_route(trajectory),
    }
    return results


def evaluate_route_map(
    trajectory: StructuralTrajectory,
    route_result: RouteMapResult,
) -> tuple[dict[str, float], dict[str, np.ndarray]]:
    structural_loss_map = trajectory.structural_loss_map
    route_loss_map = route_result.route_loss_map
    structural_action_gap, route_action_gap, round_defect = compute_action_gap_defect(
        structural_loss_map, route_loss_map
    )
    evaluation = trajectory.evaluation_slice
    structural_minimum = np.min(structural_loss_map, axis=1)
    structural_optimal = np.isclose(
        structural_loss_map,
        structural_minimum[:, None],
        atol=1e-12,
        rtol=0.0,
    )
    route_minimum = np.min(route_loss_map, axis=1)
    route_optimal = np.isclose(
        route_loss_map,
        route_minimum[:, None],
        atol=1e-12,
        rtol=0.0,
    )
    ranking_reversal = np.any(route_optimal & ~structural_optimal, axis=1)
    structural_margin = np.full(trajectory.decision_horizon, np.inf, dtype=float)
    for round_index in range(trajectory.decision_horizon):
        suboptimal = ~structural_optimal[round_index]
        if np.any(suboptimal):
            structural_margin[round_index] = float(
                np.min(
                    structural_loss_map[round_index, suboptimal]
                    - structural_minimum[round_index]
                )
            )
    margin_preserved = round_defect < structural_margin
    route_action = np.argmin(route_loss_map, axis=1)
    route_structural_regret = (
        structural_loss_map[np.arange(trajectory.decision_horizon), route_action]
        - structural_minimum
    )
    absolute_loss_map_error = np.mean(
        np.abs(route_loss_map - structural_loss_map), axis=1
    )
    summary = {
        "population_raw_action_gap_defect": float(np.mean(round_defect[evaluation])),
        "ranking_reversal_rate": float(np.mean(ranking_reversal[evaluation])),
        "margin_preservation_rate": float(np.mean(margin_preserved[evaluation])),
        "structural_regret_per_round": float(
            np.mean(route_structural_regret[evaluation])
        ),
        "absolute_loss_map_error_appendix": float(
            np.mean(absolute_loss_map_error[evaluation])
        ),
        "minimum_attribution_mass": (
            float(np.min(route_result.attribution_diagnostics.attribution_mass[evaluation]))
            if route_result.attribution_diagnostics is not None
            else np.nan
        ),
    }
    round_level = {
        "structural_action_gap": structural_action_gap,
        "route_action_gap": route_action_gap,
        "round_action_gap_defect": round_defect,
        "ranking_reversal": ranking_reversal,
        "structural_margin": structural_margin,
        "margin_preserved": margin_preserved,
        "route_action": route_action,
        "route_structural_regret": route_structural_regret,
        "absolute_loss_map_error": absolute_loss_map_error,
    }
    return summary, round_level


def evaluate_pairwise_metrics(
    trajectory: StructuralTrajectory,
    route_result: RouteMapResult,
) -> dict[str, np.ndarray]:
    structural_action_gap = compute_action_gaps(trajectory.structural_loss_map)
    route_action_gap = compute_action_gaps(route_result.route_loss_map)
    evaluation = trajectory.evaluation_slice
    absolute_error = np.abs(route_action_gap - structural_action_gap)
    structural_sign = np.sign(structural_action_gap)
    route_sign = np.sign(route_action_gap)
    return {
        "mean_absolute_action_gap_error": np.mean(absolute_error[evaluation], axis=0),
        "action_gap_rmse": np.sqrt(np.mean(absolute_error[evaluation] ** 2, axis=0)),
        "sign_agreement_rate": np.mean(
            structural_sign[evaluation] == route_sign[evaluation], axis=0
        ),
    }

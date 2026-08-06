"""Legacy route constructions retained only for regression diagnostics."""

from __future__ import annotations

import numpy as np

from exp4.routes.source_bound import RouteMapResult
from exp4.simulation.trajectory import StructuralTrajectory, hash_array


def construct_arrival_time_route(trajectory: StructuralTrajectory) -> RouteMapResult:
    route_map = np.empty_like(trajectory.structural_loss_map)
    carried = np.full(trajectory.structural_loss_map.shape[1], 0.5, dtype=np.float64)
    for clock in range(trajectory.decision_horizon):
        arriving = trajectory.arrivals_by_clock[clock]
        if arriving:
            carried = np.mean(trajectory.structural_loss_map[np.asarray(arriving)], axis=0)
        route_map[clock] = carried
    return RouteMapResult("arrival_time", route_map, hash_array(route_map))


def construct_history_surrogate_route(trajectory: StructuralTrajectory) -> RouteMapResult:
    number_of_actions = trajectory.structural_loss_map.shape[1]
    context_distance = np.sum(
        (
            trajectory.structural_states[:, None, :]
            - trajectory.action_centers[None, :, :]
        )
        ** 2,
        axis=2,
    )
    contexts = np.argmin(context_distance, axis=1)
    histories = np.full((number_of_actions, number_of_actions), 0.5, dtype=np.float64)
    route_map = np.empty_like(trajectory.structural_loss_map)
    for clock in range(trajectory.decision_horizon):
        context = int(contexts[clock])
        arriving = trajectory.arrivals_by_clock[clock]
        if arriving:
            batch = np.mean(trajectory.structural_loss_map[np.asarray(arriving)], axis=0)
            histories[context] = 0.92 * histories[context] + 0.08 * batch
        route_map[clock] = histories[context]
    return RouteMapResult("history_surrogate", route_map, hash_array(route_map))

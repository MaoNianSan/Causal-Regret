"""Controlled source-bound invariant."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from exp4.simulation.trajectory import StructuralTrajectory, hash_array


@dataclass(frozen=True)
class RouteMapResult:
    route_id: str
    route_loss_map: np.ndarray
    route_map_hash: str
    diagnostics: object | None = None


def construct_source_bound_route(trajectory: StructuralTrajectory) -> RouteMapResult:
    route_map = trajectory.structural_loss_map.copy()
    return RouteMapResult("source_bound", route_map, hash_array(route_map))

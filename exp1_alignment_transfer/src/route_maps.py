from __future__ import annotations

"""Simulator-only construction of route-induced action-level maps."""

from dataclasses import dataclass
from typing import Any

import numpy as np

from src.contracts import ContractError, ScientificInvariantError
from src.path_generator import SharedPathBundle


@dataclass(frozen=True)
class RouteMapResult:
    seed: int
    mechanism_id: str
    route_id: str
    route_loss_matrix: np.ndarray
    route_map_age: np.ndarray
    arrival_batch_size: np.ndarray
    source_round_lists: list[list[int]]
    source_weight_lists: list[list[float]]
    route_map_updated: np.ndarray


def _evaluation_indices(bundle: SharedPathBundle) -> np.ndarray:
    rounds = bundle.structural_path.source_rounds
    idx = np.flatnonzero(rounds >= 0)
    if idx.size != bundle.learner_uniform_tape.size:
        raise ScientificInvariantError(
            "evaluation rounds and learner tape have inconsistent lengths"
        )
    return idx


def build_arrival_assigned_route_map(
    bundle: SharedPathBundle,
    aggregation: str = "uniform_mean",
    empty_clock_rule: str = "last_observation_carried_forward",
) -> RouteMapResult:
    if aggregation != "uniform_mean":
        raise ContractError(f"Unsupported arrival aggregation {aggregation!r}")
    if empty_clock_rule != "last_observation_carried_forward":
        raise ContractError(f"Unsupported empty-clock rule {empty_clock_rule!r}")

    structural = bundle.structural_path
    delays = bundle.delay_path
    source_to_index = {int(round_id): i for i, round_id in enumerate(structural.source_rounds)}
    arrivals_by_clock: dict[int, list[int]] = {}
    for source_round, arrival_clock in zip(delays.source_rounds, delays.arrival_clocks, strict=True):
        arrivals_by_clock.setdefault(int(arrival_clock), []).append(int(source_round))
    for values in arrivals_by_clock.values():
        values.sort()

    first_clock = int(np.min(structural.source_rounds))
    last_clock = int(np.max(structural.source_rounds))
    current_map: np.ndarray | None = None
    current_latest_source: int | None = None

    evaluation_maps: list[np.ndarray] = []
    ages: list[int] = []
    batch_sizes: list[int] = []
    source_lists: list[list[int]] = []
    weight_lists: list[list[float]] = []
    updated: list[bool] = []

    for clock in range(first_clock, last_clock + 1):
        sources = arrivals_by_clock.get(clock, [])
        if sources:
            indices = [source_to_index[s] for s in sources]
            current_map = np.mean(structural.structural_loss_matrix[indices], axis=0)
            current_latest_source = max(sources)
            weights = [1.0 / len(sources)] * len(sources)
            was_updated = True
        else:
            weights = []
            was_updated = False

        if clock >= 0:
            if current_map is None or current_latest_source is None:
                raise ScientificInvariantError(
                    "arrival route map is undefined at the first evaluation clock; "
                    "prehistory initialization failed"
                )
            evaluation_maps.append(current_map.copy())
            ages.append(int(clock - current_latest_source))
            batch_sizes.append(len(sources))
            source_lists.append(list(sources))
            weight_lists.append(weights)
            updated.append(was_updated)

    route_matrix = np.asarray(evaluation_maps, dtype=float)
    if route_matrix.shape != (
        bundle.learner_uniform_tape.size,
        structural.action_locations.size,
    ):
        raise ScientificInvariantError(f"unexpected arrival route-map shape {route_matrix.shape}")
    return RouteMapResult(
        seed=bundle.seed,
        mechanism_id=bundle.mechanism_id,
        route_id="arrival_assigned",
        route_loss_matrix=route_matrix,
        route_map_age=np.asarray(ages, dtype=int),
        arrival_batch_size=np.asarray(batch_sizes, dtype=int),
        source_round_lists=source_lists,
        source_weight_lists=weight_lists,
        route_map_updated=np.asarray(updated, dtype=bool),
    )


def build_source_bound_route_map(bundle: SharedPathBundle) -> RouteMapResult:
    structural = bundle.structural_path
    eval_idx = _evaluation_indices(bundle)
    eval_rounds = structural.source_rounds[eval_idx]
    matrix = structural.structural_loss_matrix[eval_idx].copy()
    return RouteMapResult(
        seed=bundle.seed,
        mechanism_id=bundle.mechanism_id,
        route_id="source_bound",
        route_loss_matrix=matrix,
        route_map_age=np.zeros(eval_idx.size, dtype=int),
        arrival_batch_size=np.ones(eval_idx.size, dtype=int),
        source_round_lists=[[int(t)] for t in eval_rounds],
        source_weight_lists=[[1.0] for _ in eval_rounds],
        route_map_updated=np.ones(eval_idx.size, dtype=bool),
    )

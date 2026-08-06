"""Single authoritative implementation of the Exp4 action-gap defect."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ActionGapDefectResult:
    structural_gaps: np.ndarray
    route_gaps: np.ndarray
    round_max_gap_defect: np.ndarray
    population_action_gap_defect: float


def action_pair_indices(num_actions: int) -> tuple[np.ndarray, np.ndarray]:
    low, high = np.triu_indices(int(num_actions), k=1)
    return low.astype(np.int64), high.astype(np.int64)


def compute_action_gaps(loss_map: np.ndarray) -> np.ndarray:
    if loss_map.ndim != 2 or loss_map.shape[1] < 2:
        raise ValueError("loss_map must be a two-dimensional action map")
    low, high = action_pair_indices(loss_map.shape[1])
    return loss_map[:, low] - loss_map[:, high]


def compute_action_gap_defect(
    structural_loss_map: np.ndarray,
    route_loss_map: np.ndarray,
) -> ActionGapDefectResult:
    if structural_loss_map.shape != route_loss_map.shape:
        raise ValueError("structural and route loss maps must have identical shapes")
    structural_gaps = compute_action_gaps(structural_loss_map)
    route_gaps = compute_action_gaps(route_loss_map)
    round_defect = np.max(np.abs(route_gaps - structural_gaps), axis=1)
    return ActionGapDefectResult(
        structural_gaps=structural_gaps,
        route_gaps=route_gaps,
        round_max_gap_defect=round_defect,
        population_action_gap_defect=float(np.mean(round_defect)),
    )

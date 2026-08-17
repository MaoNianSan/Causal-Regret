"""Single authoritative implementation of Exp4 gap discrepancies.

Exp4 v3 primary estimand ``D_pair`` is the pair-average gap discrepancy:

    D_pair = mean over evaluation rounds of
             mean over unordered action pairs of
             |route_gap - structural_gap|

The v2 worst-pair quantity ``delta_t = max_pair |route_gap - structural_gap|``
remains a secondary full-map theorem diagnostic (``A_T / T``). The two
estimands are distinct and must never be conflated.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class GapDiscrepancyResult:
    """Authoritative v3 pair-level discrepancy decomposition.

    Fields
    ------
    structural_gaps: per-round unordered-pair structural action gaps.
    route_gaps: per-round unordered-pair route action gaps.
    absolute_pairwise_error: |route_gaps - structural_gaps| per round x pair.
    round_mean_pairwise_discrepancy: mean over unordered pairs per round.
    round_max_gap_defect: max over unordered pairs per round (``delta_t``).
    population_mean_pairwise_discrepancy: mean over rounds of the pair mean
        (the v3 primary estimand ``D_pair``).
    mean_round_max_gap_defect: mean over rounds of ``delta_t``
        (``A_T / T``; the v2 secondary meaning).
    """

    structural_gaps: np.ndarray
    route_gaps: np.ndarray
    absolute_pairwise_error: np.ndarray
    round_mean_pairwise_discrepancy: np.ndarray
    round_max_gap_defect: np.ndarray
    population_mean_pairwise_discrepancy: float
    mean_round_max_gap_defect: float


@dataclass(frozen=True)
class ActionGapDefectResult:
    """LEGACY v2 result (explicitly isolated).

    ``population_action_gap_defect`` is a v2 semantic: it is the round-max
    defect averaged over rounds (``mean_round_max_gap_defect`` = ``A_T / T``).
    It is NOT the v3 pair-average primary. v3 primary consumers must call
    :func:`compute_gap_discrepancies` instead.
    """

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


def compute_gap_discrepancies(
    structural_loss_map: np.ndarray,
    route_loss_map: np.ndarray,
) -> GapDiscrepancyResult:
    """Authoritative v3 pair-level gap discrepancy computation.

    Hard invariant (also validated in tests and scientific invariants):

        0 <= round_mean_pairwise_discrepancy <= round_max_gap_defect

    and therefore

        population_mean_pairwise_discrepancy <= mean_round_max_gap_defect
    """
    if structural_loss_map.shape != route_loss_map.shape:
        raise ValueError("structural and route loss maps must have identical shapes")
    structural_gaps = compute_action_gaps(structural_loss_map)
    route_gaps = compute_action_gaps(route_loss_map)
    absolute_pairwise_error = np.abs(route_gaps - structural_gaps)
    round_mean_pairwise_discrepancy = np.mean(absolute_pairwise_error, axis=1)
    round_max_gap_defect = np.max(absolute_pairwise_error, axis=1)
    return GapDiscrepancyResult(
        structural_gaps=structural_gaps,
        route_gaps=route_gaps,
        absolute_pairwise_error=absolute_pairwise_error,
        round_mean_pairwise_discrepancy=round_mean_pairwise_discrepancy,
        round_max_gap_defect=round_max_gap_defect,
        population_mean_pairwise_discrepancy=float(np.mean(round_mean_pairwise_discrepancy)),
        mean_round_max_gap_defect=float(np.mean(round_max_gap_defect)),
    )


def compute_action_gap_defect(
    structural_loss_map: np.ndarray,
    route_loss_map: np.ndarray,
) -> ActionGapDefectResult:
    """LEGACY v2 max-only API kept for regression compatibility.

    ``population_action_gap_defect`` retains its exact v2 semantic: the
    round-max defect averaged over rounds. It must not be used by any v3
    primary consumer, and it must not be reinterpreted as the pair-average
    ``D_pair``.
    """
    result = compute_gap_discrepancies(structural_loss_map, route_loss_map)
    return ActionGapDefectResult(
        structural_gaps=result.structural_gaps,
        route_gaps=result.route_gaps,
        round_max_gap_defect=result.round_max_gap_defect,
        population_action_gap_defect=result.mean_round_max_gap_defect,
    )

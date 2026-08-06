from __future__ import annotations

import numpy as np

from exp4.metrics.action_gaps import compute_action_gap_defect
from exp4.metrics.ranking_diagnostics import (
    compute_margin_certificate_rate,
    compute_pairwise_gap_sign_disagreement_rate,
    compute_route_optimal_set_conflict_rate,
)


def test_maximum_pair_defect_matches_hand_calculation() -> None:
    structural = np.array([[0.0, 1.0, 3.0]])
    route = np.array([[0.0, 2.0, 2.0]])
    result = compute_action_gap_defect(structural, route)
    assert np.allclose(result.round_max_gap_defect, [2.0])
    assert result.population_action_gap_defect == 2.0


def test_action_invariant_shift_gives_zero_defect() -> None:
    structural = np.array([[0.1, 0.3, 0.8], [0.2, 0.4, 0.7]])
    route = structural + np.array([[2.0], [-1.0]])
    result = compute_action_gap_defect(structural, route)
    assert np.allclose(result.round_max_gap_defect, 0.0)


def test_optimal_set_conflict_differs_from_pairwise_sign_disagreement() -> None:
    structural = np.array([[0.0, 1.0, 2.0]])
    route = np.array([[0.0, 2.0, 1.0]])
    assert compute_route_optimal_set_conflict_rate(structural, route) == 0.0
    assert compute_pairwise_gap_sign_disagreement_rate(structural, route) > 0.0
    defect = compute_action_gap_defect(structural, route)
    assert compute_margin_certificate_rate(structural, defect.round_max_gap_defect) == 0.0

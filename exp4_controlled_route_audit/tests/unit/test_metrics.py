"""Unit tests for the v3 pair-average estimand and the legacy max-defect API.

The pair-average primary ``mean_pairwise_gap_discrepancy`` and the theorem-level
``round_max_gap_defect`` are distinct quantities. These tests pin that
distinction so the two estimands can never collapse again.
"""

from __future__ import annotations

import numpy as np

from exp4.metrics.action_gaps import (
    ActionGapDefectResult,
    GapDiscrepancyResult,
    compute_action_gap_defect,
    compute_action_gaps,
    compute_gap_discrepancies,
)
from exp4.metrics.ranking_diagnostics import (
    compute_margin_certificate_rate,
    compute_pairwise_gap_sign_disagreement_rate,
    compute_route_optimal_set_conflict_rate,
    structural_margin,
    ternary_sign,
)


def _toy_maps() -> tuple[np.ndarray, np.ndarray]:
    """K=3 toy: all three unordered pair errors are hand-calculable.

    Structural gaps: (0,1)=-1, (0,2)=-3, (1,2)=-2.
    Route gaps:      (0,1)= 1, (0,2)=-1, (1,2)=-2.
    Pair errors:     (0,1)= 2, (0,2)= 2, (1,2)= 0.
    """
    structural = np.array([[0.0, 1.0, 3.0]])
    route = np.array([[2.0, 1.0, 3.0]])
    return structural, route


def test_ternary_sign_semantics() -> None:
    values = np.array([0.5, 1e-14, 0.0, -1e-14, -0.5])
    assert np.array_equal(ternary_sign(values), np.array([1, 0, 0, 0, -1]))
    assert np.array_equal(ternary_sign(values, tolerance=1e-3), np.array([1, 0, 0, 0, -1]))
    # Above tolerance flips sign even for tiny positive noise.
    assert np.array_equal(ternary_sign(values, tolerance=1e-15), np.array([1, 1, 0, -1, -1]))


def test_hand_calculated_k3_pair_average() -> None:
    structural, route = _toy_maps()
    result = compute_gap_discrepancies(structural, route)
    assert isinstance(result, GapDiscrepancyResult)
    # All three unordered pair errors, hand-calculated.
    assert np.allclose(result.absolute_pairwise_error, [[2.0, 2.0, 0.0]])
    assert np.isclose(result.round_mean_pairwise_discrepancy[0], 4.0 / 3.0)
    assert np.isclose(result.population_mean_pairwise_discrepancy, 4.0 / 3.0)


def test_hand_calculated_max_defect() -> None:
    structural, route = _toy_maps()
    result = compute_gap_discrepancies(structural, route)
    assert np.isclose(result.round_max_gap_defect[0], 2.0)
    assert np.isclose(result.mean_round_max_gap_defect, 2.0)


def test_pair_average_and_max_defect_differ() -> None:
    """Mandatory guard against future estimand collapse."""
    structural, route = _toy_maps()
    result = compute_gap_discrepancies(structural, route)
    assert result.population_mean_pairwise_discrepancy != result.mean_round_max_gap_defect
    assert result.population_mean_pairwise_discrepancy < result.mean_round_max_gap_defect


def test_action_invariant_shift_gives_zero_discrepancy_and_defect() -> None:
    structural = np.array([[0.1, 0.3, 0.8], [0.2, 0.4, 0.7]])
    route = structural + np.array([[2.0], [-1.0]])
    result = compute_gap_discrepancies(structural, route)
    assert np.allclose(result.round_mean_pairwise_discrepancy, 0.0, atol=1e-15)
    assert np.allclose(result.round_max_gap_defect, 0.0, atol=1e-15)
    assert np.isclose(result.population_mean_pairwise_discrepancy, 0.0, atol=1e-15)
    assert np.isclose(result.mean_round_max_gap_defect, 0.0, atol=1e-15)


def test_round_mean_bounded_by_round_max() -> None:
    rng = np.random.default_rng(7)
    structural = rng.uniform(0.0, 1.0, size=(40, 6))
    route = rng.uniform(0.0, 1.0, size=(40, 6))
    result = compute_gap_discrepancies(structural, route)
    assert np.all(result.round_mean_pairwise_discrepancy >= -1e-15)
    assert np.all(result.round_mean_pairwise_discrepancy <= result.round_max_gap_defect + 1e-15)
    assert result.population_mean_pairwise_discrepancy <= result.mean_round_max_gap_defect + 1e-15


def test_source_bound_identity_gives_all_zero_alignment_diagnostics() -> None:
    structural = np.array([[0.0, 1.0, 3.0], [1.0, 1.5, 2.0]])
    route = structural.copy()  # exact source-labelled route
    result = compute_gap_discrepancies(structural, route)
    assert result.population_mean_pairwise_discrepancy == 0.0
    assert result.mean_round_max_gap_defect == 0.0
    assert compute_pairwise_gap_sign_disagreement_rate(structural, route) == 0.0
    assert compute_route_optimal_set_conflict_rate(structural, route) == 0.0


def test_route_optimal_conflict_differs_from_pairwise_sign_disagreement() -> None:
    structural = np.array([[0.0, 1.0, 2.0]])
    route = np.array([[0.0, 2.0, 1.0]])
    assert compute_route_optimal_set_conflict_rate(structural, route) == 0.0
    assert compute_pairwise_gap_sign_disagreement_rate(structural, route) > 0.0


def test_margin_certificate_consumes_max_defect_not_pair_average() -> None:
    """The margin certificate MUST use delta_t (max), never the pair average."""
    structural = np.array([[0.0, 1.0, 2.0]])
    route = np.array([[0.0, 2.0, 1.0]])
    result = compute_gap_discrepancies(structural, route)
    margins = structural_margin(structural)
    assert np.all(np.isfinite(margins))
    # delta_t = 2, mu = 1 -> certificate 0.
    assert compute_margin_certificate_rate(structural, result.round_max_gap_defect) == 0.0
    # Pair average (4/3) would also fail here, but a stricter case separates them:
    structural2 = np.array([[0.0, 0.9, 2.0]])
    route2 = np.array([[0.0, 1.7, 1.6]])
    result2 = compute_gap_discrepancies(structural2, route2)
    # Pair errors: |0-0.9|=0.9? no: gaps: route (0,1)=-1.7,(0,2)=-1.6,(1,2)=0.1;
    # structural: (0,1)=-0.9,(0,2)=-2.0,(1,2)=-1.1.
    # errors: 0.8, 0.4, 1.2 -> pair mean 2.4/3 = 0.8 < mu = 0.9; max = 1.2 > mu.
    assert np.isclose(result2.round_mean_pairwise_discrepancy[0], 24.0 / 30.0)
    assert result2.round_max_gap_defect[0] > structural_margin(structural2)[0]
    assert compute_margin_certificate_rate(structural2, result2.round_max_gap_defect) == 0.0


def test_legacy_action_gap_defect_api_preserves_v2_semantics() -> None:
    structural = np.array([[0.0, 1.0, 3.0]])
    route = np.array([[0.0, 2.0, 2.0]])
    result = compute_action_gap_defect(structural, route)
    assert isinstance(result, ActionGapDefectResult)
    assert np.allclose(result.round_max_gap_defect, [2.0])
    # v2 semantic: the max defect averaged over rounds.
    assert result.population_action_gap_defect == 2.0
    discrepancies = compute_gap_discrepancies(structural, route)
    assert np.isclose(result.population_action_gap_defect, discrepancies.mean_round_max_gap_defect)
    # Legacy scalar is NOT the pair average.
    assert not np.isclose(result.population_action_gap_defect, discrepancies.population_mean_pairwise_discrepancy)


def test_action_gaps_pair_layout() -> None:
    loss = np.array([[0.0, 1.0, 3.0]])
    gaps = compute_action_gaps(loss)
    assert np.allclose(gaps, [[-1.0, -3.0, -2.0]])

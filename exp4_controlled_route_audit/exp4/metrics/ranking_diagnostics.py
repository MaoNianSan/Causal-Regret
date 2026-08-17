"""Distinct optimal-set, pairwise-sign, and margin-certificate diagnostics."""

from __future__ import annotations

import numpy as np

from exp4.metrics.action_gaps import compute_action_gaps


def ternary_sign(values: np.ndarray, tolerance: float = 1e-12) -> np.ndarray:
    """Authoritative numerical ternary sign.

    x > +tol -> +1; x < -tol -> -1; otherwise -> 0. The theoretical sign map
    has sgn(0) = 0; floating-point noise must not create artificial reversals.
    """
    values = np.asarray(values, dtype=np.float64)
    sign = np.zeros(values.shape, dtype=np.int8)
    sign[values > float(tolerance)] = 1
    sign[values < -float(tolerance)] = -1
    return sign


def compute_route_optimal_set_conflict_rate(
    structural_loss_map: np.ndarray, route_loss_map: np.ndarray
) -> float:
    """Fraction of rounds with route-optimal-set conflict.

    This is the binary ``chi_t > 0`` event aggregated as a round fraction.
    It is NOT the mean of ``chi_t`` and NOT the pairwise sign disagreement
    rate; both identities are validated in tests.
    """
    structural_minimum = np.min(structural_loss_map, axis=1)
    route_minimum = np.min(route_loss_map, axis=1)
    structural_optimal = np.isclose(
        structural_loss_map, structural_minimum[:, None], atol=1e-12, rtol=0.0
    )
    route_optimal = np.isclose(
        route_loss_map, route_minimum[:, None], atol=1e-12, rtol=0.0
    )
    conflict = np.any(route_optimal & ~structural_optimal, axis=1)
    return float(np.mean(conflict))


def compute_pairwise_gap_sign_disagreement_rate(
    structural_loss_map: np.ndarray, route_loss_map: np.ndarray
) -> float:
    """Fraction of unordered action pairs whose gap signs differ.

    Uses the tolerance-consistent ternary sign (sgn(0)=0); no uncontrolled
    floating-point sign noise.
    """
    structural_sign = ternary_sign(compute_action_gaps(structural_loss_map))
    route_sign = ternary_sign(compute_action_gaps(route_loss_map))
    return float(np.mean(structural_sign != route_sign))


def structural_margin(structural_loss_map: np.ndarray) -> np.ndarray:
    minimum = np.min(structural_loss_map, axis=1)
    optimal = np.isclose(structural_loss_map, minimum[:, None], atol=1e-12, rtol=0.0)
    margins = np.full(len(structural_loss_map), np.inf, dtype=np.float64)
    for row_index, row in enumerate(structural_loss_map):
        suboptimal = ~optimal[row_index]
        if np.any(suboptimal):
            margins[row_index] = float(np.min(row[suboptimal] - minimum[row_index]))
    return margins


def compute_margin_certificate_rate(
    structural_loss_map: np.ndarray, round_max_gap_defect: np.ndarray
) -> float:
    """Margin certificate: delta_t < mu_t.

    MUST consume the round-max gap defect (``delta_t``), never the pair-average
    discrepancy. The theorem condition is ``delta_t < mu_t``; substituting the
    mean pairwise discrepancy here would be a scientific error.
    """
    margins = structural_margin(structural_loss_map)
    return float(np.mean(round_max_gap_defect < margins))

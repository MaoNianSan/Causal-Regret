"""Distinct optimal-set, pairwise-sign, and margin-certificate diagnostics."""

from __future__ import annotations

import numpy as np

from exp4.metrics.action_gaps import compute_action_gaps


def compute_route_optimal_set_conflict_rate(
    structural_loss_map: np.ndarray, route_loss_map: np.ndarray
) -> float:
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
    structural_sign = np.sign(compute_action_gaps(structural_loss_map))
    route_sign = np.sign(compute_action_gaps(route_loss_map))
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
    margins = structural_margin(structural_loss_map)
    return float(np.mean(round_max_gap_defect < margins))

"""Appendix-only regression diagnostics excluded from primary artifacts."""

from __future__ import annotations

import numpy as np


def compute_route_greedy_structural_regret(
    structural_loss_map: np.ndarray, route_loss_map: np.ndarray
) -> np.ndarray:
    route_action = np.argmin(route_loss_map, axis=1)
    structural_minimum = np.min(structural_loss_map, axis=1)
    return (
        structural_loss_map[np.arange(len(route_action)), route_action]
        - structural_minimum
    )

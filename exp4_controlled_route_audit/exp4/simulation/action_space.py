"""Finite action-space construction."""

from __future__ import annotations

import numpy as np


def construct_action_centers(num_actions: int) -> np.ndarray:
    if int(num_actions) < 2:
        raise ValueError("num_actions must be at least two")
    grid = np.linspace(-1.45, 1.45, int(num_actions), dtype=np.float64)
    centers = np.stack(
        (grid, 0.55 * np.sin(1.8 * grid), 0.35 * np.cos(1.3 * grid)), axis=1
    )
    return centers.astype(np.float64, copy=False)

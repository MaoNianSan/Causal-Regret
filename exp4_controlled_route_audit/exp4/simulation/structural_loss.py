"""Structural loss map for the controlled heterogeneous DGP."""

from __future__ import annotations

import numpy as np


def compute_structural_loss_map(
    states: np.ndarray, action_centers: np.ndarray
) -> np.ndarray:
    states_2d = np.atleast_2d(states).astype(np.float64, copy=False)
    if states_2d.shape[1] != action_centers.shape[1]:
        raise ValueError("state and action-center dimensions must match")
    squared_distance = np.sum(
        (states_2d[:, None, :] - action_centers[None, :, :]) ** 2, axis=2
    )
    nearest_action = np.argmin(squared_distance, axis=1)
    regime_floor = np.where((nearest_action % 2) == 0, 0.035, 0.285)
    shaped_distance = 1.0 - np.exp(-squared_distance / 0.24)
    losses = regime_floor[:, None] + (1.0 - regime_floor[:, None]) * shaped_distance
    return np.clip(losses, 0.0, 1.0).astype(np.float64)


def compute_smooth_robustness_loss_map(
    states: np.ndarray, action_centers: np.ndarray
) -> np.ndarray:
    """Appendix robustness loss without the parity-dependent regime floor."""
    states_2d = np.atleast_2d(states).astype(np.float64, copy=False)
    squared_distance = np.sum(
        (states_2d[:, None, :] - action_centers[None, :, :]) ** 2, axis=2
    )
    return np.clip(0.08 + 0.92 * (1.0 - np.exp(-squared_distance / 0.24)), 0.0, 1.0)

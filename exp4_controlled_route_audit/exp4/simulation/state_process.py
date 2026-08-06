"""Piecewise-stable state process with continuous transition hazard."""

from __future__ import annotations

import numpy as np


def generate_piecewise_states(
    rng: np.random.Generator,
    clock_horizon: int,
    action_centers: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    if clock_horizon <= 0:
        raise ValueError("clock_horizon must be positive")
    state_dimension = action_centers.shape[1]
    states = np.zeros((clock_horizon, state_dimension), dtype=np.float64)
    transition_hazard = np.zeros(clock_horizon, dtype=np.float64)
    clock = 0
    regime = int(rng.integers(0, len(action_centers)))
    while clock < clock_horizon:
        segment_length = int(rng.integers(26, 39))
        segment_end = min(clock_horizon, clock + segment_length)
        actual_length = segment_end - clock
        hazard_width = min(8, max(6, actual_length // 4))
        for local_index, absolute_index in enumerate(range(clock, segment_end)):
            hazard = max(0.0, (local_index - (actual_length - hazard_width) + 1) / hazard_width)
            hazard = min(1.0, hazard)
            transition_hazard[absolute_index] = hazard
            states[absolute_index] = (
                action_centers[regime]
                + np.array((0.0, 0.08 * hazard, -0.05 * hazard), dtype=float)
                + rng.normal(0.0, (0.055, 0.040, 0.035), size=state_dimension)
            )
        clock = segment_end
        alternatives = np.flatnonzero(np.arange(len(action_centers)) != regime)
        regime = int(rng.choice(alternatives))
    return np.clip(states, -1.8, 1.8), transition_hazard

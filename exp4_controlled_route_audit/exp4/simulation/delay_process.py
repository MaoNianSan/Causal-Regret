"""State-coupled integer delays with an exact realized mean."""

from __future__ import annotations

import numpy as np


def generate_exact_mean_delays(
    rng: np.random.Generator,
    transition_hazard: np.ndarray,
    delay_state_coupling: float,
    target_mean_delay: int,
    maximum_candidate_delay: int,
) -> np.ndarray:
    number_of_rounds = len(transition_hazard)
    if number_of_rounds == 0:
        raise ValueError("transition_hazard must be non-empty")
    standardized = (transition_hazard - float(np.mean(transition_hazard))) / (
        float(np.std(transition_hazard)) + 1e-12
    )
    raw_delay = (
        float(target_mean_delay)
        + float(delay_state_coupling) * 1.55 * standardized
        + rng.normal(0.0, 0.70, size=number_of_rounds)
    )
    delays = np.clip(
        np.rint(raw_delay).astype(np.int64), 1, int(maximum_candidate_delay)
    )
    target_total = int(target_mean_delay) * number_of_rounds
    remaining = int(target_total - int(np.sum(delays)))
    increment_order = np.argsort(-standardized, kind="stable")
    decrement_order = np.argsort(standardized, kind="stable")
    cursor = 0
    while remaining > 0:
        index = int(increment_order[cursor % number_of_rounds])
        if delays[index] < maximum_candidate_delay:
            delays[index] += 1
            remaining -= 1
        cursor += 1
    cursor = 0
    while remaining < 0:
        index = int(decrement_order[cursor % number_of_rounds])
        if delays[index] > 1:
            delays[index] -= 1
            remaining += 1
        cursor += 1
    if int(np.sum(delays)) != target_total:
        raise RuntimeError("Exact mean-delay calibration failed")
    return delays

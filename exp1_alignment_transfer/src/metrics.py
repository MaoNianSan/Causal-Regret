from __future__ import annotations

"""Frozen scientific quantities for Experiment 1."""

import numpy as np

from src.contracts import ScientificInvariantError


def action_gap_defect(route_loss: np.ndarray, structural_loss: np.ndarray) -> np.ndarray:
    route = np.asarray(route_loss, dtype=float)
    structural = np.asarray(structural_loss, dtype=float)
    if route.shape != structural.shape:
        raise ScientificInvariantError("route and structural loss matrices must have equal shape")
    error = route - structural
    return np.max(error, axis=1) - np.min(error, axis=1)


def action_gap_defect_bruteforce(route_loss: np.ndarray, structural_loss: np.ndarray) -> np.ndarray:
    route = np.asarray(route_loss, dtype=float)
    structural = np.asarray(structural_loss, dtype=float)
    out = np.empty(route.shape[0], dtype=float)
    for t in range(route.shape[0]):
        route_gap = route[t, :, None] - route[t, None, :]
        structural_gap = structural[t, :, None] - structural[t, None, :]
        out[t] = float(np.max(np.abs(route_gap - structural_gap)))
    return out


def optimal_mask(loss: np.ndarray, tolerance: float = 1e-12) -> np.ndarray:
    values = np.asarray(loss, dtype=float)
    return values <= np.min(values, axis=1, keepdims=True) + float(tolerance)


def deterministic_best_action(loss: np.ndarray) -> np.ndarray:
    return np.argmin(np.asarray(loss, dtype=float), axis=1).astype(int)


def structural_regret_increment(actions: np.ndarray, structural_loss: np.ndarray) -> np.ndarray:
    actions = np.asarray(actions, dtype=int)
    loss = np.asarray(structural_loss, dtype=float)
    rows = np.arange(loss.shape[0])
    return loss[rows, actions] - np.min(loss, axis=1)


def route_regret_increment(actions: np.ndarray, route_loss: np.ndarray) -> np.ndarray:
    actions = np.asarray(actions, dtype=int)
    loss = np.asarray(route_loss, dtype=float)
    rows = np.arange(loss.shape[0])
    return loss[rows, actions] - np.min(loss, axis=1)


def structural_margin(structural_loss: np.ndarray, tolerance: float = 1e-12) -> np.ndarray:
    values = np.asarray(structural_loss, dtype=float)
    mask = optimal_mask(values, tolerance)
    minima = np.min(values, axis=1)
    out = np.empty(values.shape[0], dtype=float)
    for i in range(values.shape[0]):
        remaining = values[i, ~mask[i]]
        out[i] = float(np.min(remaining) - minima[i]) if remaining.size else np.inf
    return out


def ranking_reversal(
    route_loss: np.ndarray, structural_loss: np.ndarray, tolerance: float = 1e-12
) -> np.ndarray:
    route_best = optimal_mask(route_loss, tolerance)
    structural_best = optimal_mask(structural_loss, tolerance)
    # Reversal occurs when the route-optimal set is not a subset of structural optimal set.
    return np.any(route_best & ~structural_best, axis=1)


def reversal_margin(
    route_loss: np.ndarray, structural_loss: np.ndarray, tolerance: float = 1e-12
) -> np.ndarray:
    route_best = optimal_mask(route_loss, tolerance)
    minima = np.min(structural_loss, axis=1)
    out = np.zeros(structural_loss.shape[0], dtype=float)
    for i in range(structural_loss.shape[0]):
        selected = structural_loss[i, route_best[i]]
        out[i] = float(np.min(selected) - minima[i])
    return out


def margin_preservation(delta: np.ndarray, margin: np.ndarray) -> np.ndarray:
    return np.asarray(delta, dtype=float) < np.asarray(margin, dtype=float)


def transfer_slack(
    structural_regret: float,
    route_regret: float,
    alignment_budget: float,
    horizon: int,
) -> tuple[float, float]:
    rate = (float(route_regret) + float(alignment_budget) - float(structural_regret)) / int(horizon)
    tolerance = 1e-8 * max(
        1.0,
        float(structural_regret) / int(horizon),
        (float(route_regret) + float(alignment_budget)) / int(horizon),
    )
    return float(rate), float(tolerance)

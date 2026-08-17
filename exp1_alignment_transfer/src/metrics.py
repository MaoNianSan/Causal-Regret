from __future__ import annotations

"""Frozen scientific quantities for Experiment 1."""

import numpy as np

from src.contracts import ScientificInvariantError


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
    # Legacy binary event, defined as chi_t > 0: the route-optimal set is not
    # a subset of the structural optimal set. Kept for legacy continuity and
    # validated as (directed_choice_disagreement > 0) up to tolerance.
    return directed_choice_disagreement(
        route_loss, structural_loss, tolerance=tolerance
    ) > 0.0


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


def pairwise_sign_disagreement(
    route_loss: np.ndarray,
    structural_loss: np.ndarray,
    tolerance: float = 1e-12,
) -> np.ndarray:
    """Per-round pairwise ordinal disagreement rho_t in [0, 1].

    Each unordered action pair is used exactly once. rho_t is the fraction of
    unordered pairs whose ternary gap signs differ between the route and the
    structural loss. This is NOT ranking_reversal and NOT mean chi.
    """
    route = np.asarray(route_loss, dtype=float)
    structural = np.asarray(structural_loss, dtype=float)
    if route.shape != structural.shape:
        raise ScientificInvariantError("route and structural loss matrices must have equal shape")
    if route.shape[1] < 2:
        return np.zeros(route.shape[0], dtype=float)
    low, high = np.triu_indices(int(route.shape[1]), k=1)
    route_gaps = route[:, low] - route[:, high]
    structural_gaps = structural[:, low] - structural[:, high]
    route_sign = ternary_sign(route_gaps, tolerance)
    structural_sign = ternary_sign(structural_gaps, tolerance)
    return np.mean(route_sign != structural_sign, axis=1).astype(float)


def directed_choice_disagreement(
    route_loss: np.ndarray,
    structural_loss: np.ndarray,
    tolerance: float = 1e-12,
) -> np.ndarray:
    """Per-round directed choice disagreement chi_t = |A_r* \\ A_c*| / |A_r*|.

    Range [0, 1]. This is the exact manuscript chi_t quantity.
    ranking_reversal is the binary event chi_t > 0.
    """
    route = np.asarray(route_loss, dtype=float)
    structural = np.asarray(structural_loss, dtype=float)
    if route.shape != structural.shape:
        raise ScientificInvariantError("route and structural loss matrices must have equal shape")
    route_best = optimal_mask(route, tolerance)
    structural_best = optimal_mask(structural, tolerance)
    nonstructural = route_best & ~structural_best
    counts = np.sum(nonstructural, axis=1).astype(float)
    sizes = np.sum(route_best, axis=1).astype(float)
    return counts / sizes


def complete_conflict_indicator(
    route_loss: np.ndarray,
    structural_loss: np.ndarray,
    tolerance: float = 1e-12,
) -> np.ndarray:
    """True iff the route-optimal set and structural-optimal set are disjoint.

    Equivalent to chi_t == 1 within tolerance-consistent optimal-set
    semantics (validated in tests).
    """
    chi = directed_choice_disagreement(route_loss, structural_loss, tolerance)
    return np.isclose(chi, 1.0, atol=1e-15, rtol=0.0)


def structural_conflict_margin(
    route_loss: np.ndarray,
    structural_loss: np.ndarray,
    tolerance: float = 1e-12,
) -> np.ndarray:
    """gamma_t = min_{b in A_r*} [L_c(b) - min L_c] on complete-conflict rounds.

    Returns NaN outside complete conflict (never silently 0).
    """
    route = np.asarray(route_loss, dtype=float)
    structural = np.asarray(structural_loss, dtype=float)
    if route.shape != structural.shape:
        raise ScientificInvariantError("route and structural loss matrices must have equal shape")
    conflict = complete_conflict_indicator(route, structural, tolerance)
    route_best = optimal_mask(route, tolerance)
    minima = np.min(structural, axis=1)
    out = np.full(route.shape[0], np.nan, dtype=float)
    for i in range(route.shape[0]):
        if not conflict[i]:
            continue
        selected = structural[i, route_best[i]]
        out[i] = float(np.min(selected) - minima[i])
    return out


def route_conflict_margin(
    route_loss: np.ndarray,
    structural_loss: np.ndarray,
    tolerance: float = 1e-12,
) -> np.ndarray:
    """eta_t = min_{a notin A_r*} [L_r(a) - min L_r] on complete-conflict rounds.

    Returns NaN outside complete conflict (never silently 0). If every route
    action is optimal the complement is empty and eta is NaN (never
    manufactured).
    """
    route = np.asarray(route_loss, dtype=float)
    structural = np.asarray(structural_loss, dtype=float)
    if route.shape != structural.shape:
        raise ScientificInvariantError("route and structural loss matrices must have equal shape")
    conflict = complete_conflict_indicator(route, structural, tolerance)
    route_best = optimal_mask(route, tolerance)
    minima = np.min(route, axis=1)
    out = np.full(route.shape[0], np.nan, dtype=float)
    for i in range(route.shape[0]):
        if not conflict[i]:
            continue
        remaining = route[i, ~route_best[i]]
        if remaining.size == 0:
            # Degenerate case: every route action is optimal. Never
            # manufacture eta.
            continue
        out[i] = float(np.min(remaining) - minima[i])
    return out


def regret_stability_slack(
    structural_regret: float,
    route_regret: float,
    alignment_budget: float,
    horizon: int,
) -> tuple[float, float]:
    """Two-sided sharp regret stability |R_c - R_r| <= A, rate-divided.

    Returns (rate, tolerance) with

        rate = (A - |R_c - R_r|) / T

    The required invariant is ``rate >= -tolerance``.
    """
    slack = float(alignment_budget) - abs(float(structural_regret) - float(route_regret))
    rate = slack / int(horizon)
    tolerance = 1e-8 * max(
        1.0,
        float(alignment_budget) / int(horizon),
        abs(float(structural_regret) - float(route_regret)) / int(horizon),
    )
    return float(rate), float(tolerance)


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

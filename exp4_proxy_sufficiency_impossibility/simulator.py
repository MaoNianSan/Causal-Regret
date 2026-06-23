"""Controlled delayed-feedback simulator with matched mean delay and emitted proxies."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from config import (
    CONTEXT_PROXY_SIGMA,
    K_ACTIONS,
    MAX_DELAY,
    PROXY_SIGMAS,
    STATE_DIM,
    TARGET_MEAN_DELAY,
)


@dataclass(frozen=True)
class Trace:
    seed: int
    T: int
    states: np.ndarray
    action_centers: np.ndarray
    potential_losses: np.ndarray
    delays: np.ndarray
    arrivals: tuple[tuple[int, ...], ...]
    label_uniforms: np.ndarray
    coupling_score: np.ndarray
    observed_proxy_bank: dict[float, np.ndarray]

    @property
    def mean_delay(self) -> float:
        return float(np.mean(self.delays))

    @property
    def pending_at_horizon(self) -> int:
        return int(np.sum(np.arange(self.T) + self.delays >= self.T))


def _proxy_key(sigma: float) -> float:
    return round(float(sigma), 8)


def observed_measurement(trace: Trace, sigma: float) -> np.ndarray:
    """Return a simulator-emitted decision-time observation without latent access."""
    key = _proxy_key(sigma)
    if key not in trace.observed_proxy_bank:
        available = sorted(trace.observed_proxy_bank)
        raise KeyError(f"No emitted proxy for sigma={sigma}; available={available}")
    return trace.observed_proxy_bank[key]


def _action_centers() -> np.ndarray:
    grid = np.linspace(-1.45, 1.45, K_ACTIONS)
    return np.stack([grid, 0.55 * np.sin(1.8 * grid), 0.35 * np.cos(1.3 * grid)], axis=1)


def deterministic_loss_map(states: np.ndarray, centers: np.ndarray) -> np.ndarray:
    """State-dependent loss map without the independent simulation noise term.

    This helper is used only by environment-side diagnostics.  Policies never call it.
    """
    states_2d = np.atleast_2d(states)
    dist2 = ((states_2d[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
    true_arm = np.argmin(dist2, axis=1)
    regime_floor = np.where((true_arm % 2) == 0, 0.035, 0.285)
    shape = 1.0 - np.exp(-dist2 / 0.24)
    losses = np.clip(regime_floor[:, None] + (1.0 - regime_floor[:, None]) * shape, 0.0, 1.0)
    return losses


def measurement_diagnostics(trace: Trace, sigma: float) -> tuple[float, float, float]:
    """Environment-side diagnostics, not inputs to a deployable policy.

    ``absolute_proxy_distortion_per_round`` is the action-averaged absolute gap
    between the deterministic structural loss map evaluated at the latent state and
    at the noisy proxy state.  It quantifies measurement-induced target distortion,
    not an online learner's observed loss.
    """
    proxy = observed_measurement(trace, sigma)
    error = float(np.mean(np.linalg.norm(proxy - trace.states, axis=1)))
    proxy_action = np.argmin(((proxy[:, None, :] - trace.action_centers[None, :, :]) ** 2).sum(axis=2), axis=1)
    true_action = np.argmin(trace.potential_losses, axis=1)
    reversal = float(np.mean(proxy_action != true_action))
    true_map = deterministic_loss_map(trace.states, trace.action_centers)
    proxy_map = deterministic_loss_map(proxy, trace.action_centers)
    distortion = float(np.mean(np.abs(true_map - proxy_map)))
    return error, reversal, distortion


def _generate_states(rng: np.random.Generator, T: int, centers: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Piecewise-stable state with a pre-switch hazard used only for delay coupling."""
    states = np.zeros((T, STATE_DIM), dtype=float)
    hazard = np.zeros(T, dtype=float)
    t = 0
    mode = int(rng.integers(0, len(centers)))
    while t < T:
        length = int(rng.integers(26, 39))
        end = min(T, t + length)
        hazard_width = min(8, max(6, (end - t) // 4))
        for j, idx in enumerate(range(t, end)):
            h = max(0.0, (j - ((end - t) - hazard_width) + 1) / hazard_width)
            h = min(1.0, h)
            hazard[idx] = h
            states[idx] = centers[mode] + np.array([0.0, 0.08 * h, -0.05 * h]) + rng.normal(
                0.0, [0.055, 0.040, 0.035], size=STATE_DIM
            )
        t = end
        candidates = [a for a in range(len(centers)) if a != mode]
        mode = int(rng.choice(candidates))
    return np.clip(states, -1.8, 1.8), hazard


def _exact_matched_delays(rng: np.random.Generator, score: np.ndarray, beta: float) -> np.ndarray:
    """Integer delays with exactly ``TARGET_MEAN_DELAY`` for every seed × beta."""
    T = len(score)
    z = (score - score.mean()) / (score.std() + 1e-12)
    jitter = rng.normal(0.0, 0.70, size=T)
    raw = TARGET_MEAN_DELAY + beta * 1.55 * z + jitter
    delay = np.clip(np.rint(raw).astype(int), 1, MAX_DELAY)
    target_total = TARGET_MEAN_DELAY * T
    delta = int(target_total - delay.sum())
    hi = np.argsort(-z, kind="stable")
    lo = np.argsort(z, kind="stable")
    if delta > 0:
        cursor = 0
        while delta > 0:
            i = int(hi[cursor % T])
            if delay[i] < MAX_DELAY:
                delay[i] += 1
                delta -= 1
            cursor += 1
    elif delta < 0:
        cursor = 0
        while delta < 0:
            i = int(lo[cursor % T])
            if delay[i] > 1:
                delay[i] -= 1
                delta += 1
            cursor += 1
    assert int(delay.sum()) == target_total
    return delay


def generate_trace(seed: int, T: int, beta: float) -> Trace:
    rng = np.random.default_rng(100_003 + seed)
    centers = _action_centers()
    states, coupling_score = _generate_states(rng, T, centers)
    base_losses = deterministic_loss_map(states, centers)
    noise = rng.normal(0.0, 0.009, size=(T, K_ACTIONS))
    potential_losses = np.clip(base_losses + noise, 0.0, 1.0)
    coupling_score = (coupling_score > 0.0).astype(float)
    delays = _exact_matched_delays(np.random.default_rng(200_003 + seed), coupling_score, beta)
    arrivals_lists: list[list[int]] = [[] for _ in range(T)]
    for source, delay in enumerate(delays):
        arrival = source + int(delay)
        if arrival < T:
            arrivals_lists[arrival].append(source)

    # The complete proxy arrays are materialized by the environment but policies
    # access only indices at or before their current decision/arrival time.
    measurement_noise = np.random.default_rng(400_003 + seed).normal(size=(T, STATE_DIM))
    proxy_scales = sorted({_proxy_key(x) for x in [*PROXY_SIGMAS, CONTEXT_PROXY_SIGMA]})
    observed_proxy_bank = {_proxy_key(sigma): states + float(sigma) * measurement_noise for sigma in proxy_scales}
    return Trace(
        seed=seed,
        T=T,
        states=states,
        action_centers=centers,
        potential_losses=potential_losses,
        delays=delays,
        arrivals=tuple(tuple(x) for x in arrivals_lists),
        label_uniforms=np.random.default_rng(300_003 + seed).random(T),
        coupling_score=coupling_score,
        observed_proxy_bank=observed_proxy_bank,
    )


def trace_diagnostics(trace: Trace) -> dict[str, float]:
    mismatch: list[float] = []
    reversal: list[float] = []
    best = np.argmin(trace.potential_losses, axis=1)
    for arrival_t, sources in enumerate(trace.arrivals):
        for source_t in sources:
            mismatch.append(float(np.linalg.norm(trace.states[source_t] - trace.states[arrival_t])))
            reversal.append(float(best[source_t] != best[arrival_t]))
    pending = trace.pending_at_horizon
    return {
        "mean_delay": trace.mean_delay,
        "pending_at_horizon": pending,
        "pending_fraction": float(pending / trace.T),
        "source_state_mismatch": float(np.mean(mismatch)) if mismatch else 0.0,
        "ranking_reversal_rate": float(np.mean(reversal)) if reversal else 0.0,
    }

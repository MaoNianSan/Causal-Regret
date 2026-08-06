"""Pure candidate-set and attribution-weight operations."""

from __future__ import annotations

import numpy as np


def candidate_sources(
    arrival_clock: int, decision_horizon: int, maximum_candidate_delay: int
) -> np.ndarray:
    lower = max(0, int(arrival_clock) - int(maximum_candidate_delay))
    upper = min(int(arrival_clock), int(decision_horizon))
    candidates = np.arange(lower, upper, dtype=np.int64)
    if candidates.size == 0:
        raise RuntimeError(f"No historical candidates at arrival_clock={arrival_clock}")
    if np.any(candidates >= int(arrival_clock)):
        raise RuntimeError("Candidate set contains present or future information")
    return candidates


def compute_candidate_weights(
    candidate_source_proxy: np.ndarray,
    arrival_signature: np.ndarray,
    candidate_delays: np.ndarray,
    kernel_bandwidth: float,
    delay_prior: np.ndarray,
) -> np.ndarray:
    if kernel_bandwidth <= 0.0 or not np.isfinite(kernel_bandwidth):
        raise ValueError("kernel_bandwidth must be finite and positive")
    candidate_source_proxy = np.asarray(candidate_source_proxy, dtype=np.float64)
    arrival_signature = np.asarray(arrival_signature, dtype=np.float64)
    candidate_delays = np.asarray(candidate_delays, dtype=np.int64)
    delay_prior = np.asarray(delay_prior, dtype=np.float64)
    if candidate_source_proxy.ndim != 2 or arrival_signature.ndim != 1:
        raise ValueError("proxy inputs have invalid dimensions")
    if len(candidate_source_proxy) != len(candidate_delays):
        raise ValueError("candidate proxies and delays must align")
    if np.any(candidate_delays < 1) or np.any(candidate_delays > len(delay_prior)):
        raise ValueError("candidate delay is outside calibrated support")
    prior_mass = delay_prior[candidate_delays - 1]
    if np.any(prior_mass <= 0.0) or not np.all(np.isfinite(prior_mass)):
        raise ValueError("delay prior must be finite and strictly positive")
    difference = candidate_source_proxy - arrival_signature[None, :]
    squared_distance = np.einsum("ij,ij->i", difference, difference, optimize=True)
    log_weights = -squared_distance / (2.0 * float(kernel_bandwidth) ** 2) + np.log(prior_mass)
    if not np.all(np.isfinite(log_weights)):
        raise RuntimeError("Candidate log weights are non-finite")
    log_weights -= float(np.max(log_weights))
    weights = np.exp(log_weights)
    total_mass = float(np.sum(weights))
    if not np.isfinite(total_mass) or total_mass <= 0.0:
        raise RuntimeError("Candidate weights have invalid total mass")
    weights /= total_mass
    if not np.isclose(float(np.sum(weights)), 1.0, atol=1e-12, rtol=0.0):
        raise RuntimeError("Candidate weights do not normalize to one")
    return weights

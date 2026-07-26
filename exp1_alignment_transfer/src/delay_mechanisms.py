from __future__ import annotations

"""Policy-independent delay paths for Experiment 1."""

from dataclasses import dataclass
import hashlib
from typing import Any

import numpy as np

from config import DelayConfig
from src.artifact_io import hash_payload
from src.contracts import ContractError, ScientificInvariantError
from src.structural_process import StructuralPath


@dataclass(frozen=True)
class DelayPath:
    seed: int
    mechanism_id: str
    source_rounds: np.ndarray
    delays: np.ndarray
    arrival_clocks: np.ndarray
    delay_parameter_payload: dict[str, Any]
    generated_mean_delay: float
    delay_path_id: str
    delay_path_hash: str


def _array_hash(*arrays: np.ndarray, payload: dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(hash_payload(payload).encode("ascii"))
    for array in arrays:
        arr = np.ascontiguousarray(array)
        h.update(str(arr.dtype).encode("ascii"))
        h.update(str(arr.shape).encode("ascii"))
        h.update(arr.tobytes())
    return h.hexdigest()


def _uniforms(seed: int, size: int, stream_offset: int = 200_000) -> np.ndarray:
    return np.random.default_rng(int(seed) + stream_offset).random(int(size))


def _truncated_geometric_from_uniform(
    uniforms: np.ndarray, p: np.ndarray | float, d_max: int
) -> np.ndarray:
    u = np.clip(np.asarray(uniforms, dtype=float), 0.0, 1.0 - 1e-15)
    pp = np.clip(np.asarray(p, dtype=float), 1e-12, 1.0)
    pp = np.broadcast_to(pp, u.shape)
    q = 1.0 - pp
    out = np.zeros(u.shape, dtype=int)
    nonzero_q = q > 1e-14
    if np.any(nonzero_q):
        qn = q[nonzero_q]
        un = u[nonzero_q]
        normalizer = 1.0 - qn ** (int(d_max) + 1)
        rhs = np.clip(1.0 - un * normalizer, 1e-300, 1.0)
        k = np.ceil(np.log(rhs) / np.log(qn)).astype(int) - 1
        out[nonzero_q] = np.clip(k, 0, int(d_max))
    return out


def truncated_geometric_mean(p: float, d_max: int) -> float:
    p = float(np.clip(p, 1e-12, 1.0))
    if p >= 1.0 - 1e-14:
        return 0.0
    q = 1.0 - p
    k = np.arange(int(d_max) + 1, dtype=float)
    weights = p * q**k
    weights /= weights.sum()
    return float(np.sum(k * weights))


def solve_geometric_probability(target_mean: float, d_max: int) -> float:
    lo, hi = 1e-6, 1.0 - 1e-10
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        value = truncated_geometric_mean(mid, d_max)
        if value > target_mean:
            lo = mid
        else:
            hi = mid
    return float(0.5 * (lo + hi))


def _make_path(
    structural_path: StructuralPath,
    mechanism_id: str,
    delays: np.ndarray,
    payload: dict[str, Any],
) -> DelayPath:
    delays = np.asarray(delays, dtype=int)
    rounds = structural_path.source_rounds.astype(int, copy=True)
    arrivals = rounds + delays
    full_payload = {
        "seed": structural_path.seed,
        "mechanism_id": mechanism_id,
        **payload,
    }
    path_hash = _array_hash(rounds, delays, arrivals, payload=full_payload)
    return DelayPath(
        seed=structural_path.seed,
        mechanism_id=mechanism_id,
        source_rounds=rounds,
        delays=delays,
        arrival_clocks=arrivals,
        delay_parameter_payload=full_payload,
        generated_mean_delay=float(np.mean(delays)),
        delay_path_id=f"{mechanism_id}:{structural_path.seed}:{path_hash[:16]}",
        delay_path_hash=path_hash,
    )


def generate_zero_delay(structural_path: StructuralPath) -> DelayPath:
    delays = np.zeros(structural_path.source_rounds.size, dtype=int)
    return _make_path(structural_path, "zero_delay", delays, {"delay_value": 0})


def generate_fixed_delay(structural_path: StructuralPath, delay_value: int) -> DelayPath:
    if delay_value < 0:
        raise ContractError("fixed delay must be nonnegative")
    delays = np.full(structural_path.source_rounds.size, int(delay_value), dtype=int)
    return _make_path(
        structural_path,
        "fixed_delay",
        delays,
        {"delay_value": int(delay_value)},
    )


def generate_geometric_delay(
    structural_path: StructuralPath,
    p: float,
    d_max: int,
    stream_offset: int = 200_000,
) -> DelayPath:
    u = _uniforms(structural_path.seed, structural_path.source_rounds.size, stream_offset)
    delays = _truncated_geometric_from_uniform(u, float(p), int(d_max))
    return _make_path(
        structural_path,
        "geometric_delay",
        delays,
        {"p": float(p), "d_max": int(d_max), "uniform_stream_offset": stream_offset},
    )


def generate_mixture_delay(
    structural_path: StructuralPath,
    mixture_weight_fast: float,
    d_max: int,
    p_fast: float = 1.0 / 3.0,
    p_slow: float = 1.0 / 31.0,
) -> DelayPath:
    n = structural_path.source_rounds.size
    u_len = _uniforms(structural_path.seed, n, 200_000)
    u_mix = _uniforms(structural_path.seed, n, 210_000)
    fast = _truncated_geometric_from_uniform(u_len, p_fast, d_max)
    slow = _truncated_geometric_from_uniform(u_len, p_slow, d_max)
    w = float(mixture_weight_fast)
    if not 0.0 <= w <= 1.0:
        raise ContractError("mixture_weight_fast must lie in [0,1]")
    delays = np.where(u_mix < w, fast, slow)
    return _make_path(
        structural_path,
        "mixture_delay",
        delays,
        {
            "mixture_weight_fast": w,
            "p_fast": float(p_fast),
            "p_slow": float(p_slow),
            "d_max": int(d_max),
        },
    )


def generate_state_coupled_delay(
    structural_path: StructuralPath,
    intercept: float,
    beta: float,
    d_max: int,
) -> DelayPath:
    u = _uniforms(structural_path.seed, structural_path.source_rounds.size, 200_000)
    logits = float(intercept) + float(beta) * structural_path.structural_state
    p = 1.0 / (1.0 + np.exp(-logits))
    delays = _truncated_geometric_from_uniform(u, p, d_max)
    return _make_path(
        structural_path,
        "state_coupled_delay",
        delays,
        {
            "intercept": float(intercept),
            "beta": float(beta),
            "d_max": int(d_max),
        },
    )


def solve_mixture_weight(
    target_mean: float,
    d_max: int,
    p_fast: float = 1.0 / 3.0,
    p_slow: float = 1.0 / 31.0,
) -> float:
    mean_fast = truncated_geometric_mean(p_fast, d_max)
    mean_slow = truncated_geometric_mean(p_slow, d_max)
    if not min(mean_fast, mean_slow) <= target_mean <= max(mean_fast, mean_slow):
        raise ContractError(
            f"target mean {target_mean} outside component means [{mean_fast},{mean_slow}]"
        )
    return float((mean_slow - target_mean) / (mean_slow - mean_fast))


def solve_state_coupled_intercept(
    structural_paths: list[StructuralPath],
    beta: float,
    d_max: int,
    target_mean: float,
) -> float:
    states = np.concatenate([path.structural_state for path in structural_paths])
    uniforms = np.concatenate(
        [_uniforms(path.seed, path.source_rounds.size, 200_000) for path in structural_paths]
    )

    def realised_mean(intercept: float) -> float:
        p = 1.0 / (1.0 + np.exp(-(intercept + float(beta) * states)))
        return float(np.mean(_truncated_geometric_from_uniform(uniforms, p, d_max)))

    lo, hi = -12.0, 8.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        value = realised_mean(mid)
        if value > target_mean:
            lo = mid
        else:
            hi = mid
    return float(0.5 * (lo + hi))


def validate_delay_path(path: DelayPath, structural_path: StructuralPath, d_max: int) -> dict[str, Any]:
    same_rounds = bool(np.array_equal(path.source_rounds, structural_path.source_rounds))
    finite = bool(np.all(np.isfinite(path.delays)))
    integer = bool(np.issubdtype(path.delays.dtype, np.integer))
    support = bool(np.all((path.delays >= 0) & (path.delays <= int(d_max))))
    arrivals_correct = bool(np.array_equal(path.arrival_clocks, path.source_rounds + path.delays))
    report = {
        "same_source_rounds": same_rounds,
        "finite_delays": finite,
        "integer_delays": integer,
        "delay_support_valid": support,
        "arrival_clocks_correct": arrivals_correct,
        "generated_mean_delay": float(np.mean(path.delays)),
        "delay_sd": float(np.std(path.delays)),
        "delay_q50": float(np.quantile(path.delays, 0.50)),
        "delay_q90": float(np.quantile(path.delays, 0.90)),
        "delay_q99": float(np.quantile(path.delays, 0.99)),
        "delay_path_id": path.delay_path_id,
        "delay_path_hash": path.delay_path_hash,
    }
    if not all([same_rounds, finite, integer, support, arrivals_correct]):
        raise ScientificInvariantError(f"Invalid delay path: {report}")
    return report

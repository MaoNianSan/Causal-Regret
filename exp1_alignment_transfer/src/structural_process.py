from __future__ import annotations

"""Controlled structural data-generating processes for Experiment 1."""

from dataclasses import dataclass
import hashlib
from typing import Any

import numpy as np

from config import StructuralConfig
from src.artifact_io import hash_payload
from src.contracts import ContractError, ScientificInvariantError


@dataclass(frozen=True)
class StructuralPath:
    seed: int
    structural_family_id: str
    source_rounds: np.ndarray
    latent_raw_state: np.ndarray
    structural_state: np.ndarray
    public_context: np.ndarray
    action_locations: np.ndarray
    structural_loss_matrix: np.ndarray
    structural_best_mask: np.ndarray
    structural_margin: np.ndarray
    path_id: str
    path_hash: str
    parameter_payload: dict[str, Any]


def _array_hash(*arrays: np.ndarray, payload: dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(hash_payload(payload).encode("ascii"))
    for array in arrays:
        arr = np.ascontiguousarray(array)
        h.update(str(arr.dtype).encode("ascii"))
        h.update(str(arr.shape).encode("ascii"))
        h.update(arr.tobytes())
    return h.hexdigest()


def action_locations(k_actions: int) -> np.ndarray:
    if k_actions < 2:
        raise ContractError("k_actions must be at least 2")
    return np.linspace(-1.0, 1.0, int(k_actions), dtype=float)


def _best_mask_and_margin(loss: np.ndarray, tolerance: float) -> tuple[np.ndarray, np.ndarray]:
    minima = np.min(loss, axis=1, keepdims=True)
    best = loss <= minima + float(tolerance)
    margins = np.empty(loss.shape[0], dtype=float)
    for i in range(loss.shape[0]):
        nonbest = loss[i, ~best[i]]
        margins[i] = float(np.min(nonbest) - minima[i, 0]) if nonbest.size else np.inf
    return best, margins


def _source_rounds(config: StructuralConfig) -> np.ndarray:
    return np.arange(-config.prehistory_length, config.horizon, dtype=int)


def generate_smooth_bounded_ar1_path(config: StructuralConfig, seed: int) -> StructuralPath:
    n_source = config.prehistory_length + config.horizon
    total = config.state_burn_in + n_source
    state_rng = np.random.default_rng(int(seed) + 100_000)
    context_rng = np.random.default_rng(int(seed) + 110_000)

    raw_all = np.empty(total, dtype=float)
    z = 0.0
    for idx in range(total):
        z = config.ar_coefficient * z + state_rng.normal(0.0, config.innovation_sd)
        raw_all[idx] = z
    raw = raw_all[config.state_burn_in :]
    state = np.tanh(raw)
    context = np.tanh(raw + context_rng.normal(0.0, config.context_noise_sd, size=n_source))
    mu = action_locations(config.k_actions)
    loss = ((state[:, None] - mu[None, :]) / 2.0) ** 2
    best, margin = _best_mask_and_margin(loss, config.tie_tolerance)
    rounds = _source_rounds(config)
    payload = {
        "seed": int(seed),
        "structural_family_id": "smooth_bounded_ar1",
        "ar_coefficient": config.ar_coefficient,
        "innovation_sd": config.innovation_sd,
        "context_noise_sd": config.context_noise_sd,
        "state_burn_in": config.state_burn_in,
        "prehistory_length": config.prehistory_length,
        "horizon": config.horizon,
        "k_actions": config.k_actions,
    }
    path_hash = _array_hash(rounds, raw, state, context, mu, loss, best, margin, payload=payload)
    return StructuralPath(
        seed=int(seed),
        structural_family_id="smooth_bounded_ar1",
        source_rounds=rounds,
        latent_raw_state=raw,
        structural_state=state,
        public_context=context,
        action_locations=mu,
        structural_loss_matrix=loss,
        structural_best_mask=best,
        structural_margin=margin,
        path_id=f"smooth_bounded_ar1:{seed}:{path_hash[:16]}",
        path_hash=path_hash,
        parameter_payload=payload,
    )


def generate_exact_valid_shift_path(
    base_random_path: StructuralPath,
    reference_action_index: int | None = None,
    tie_tolerance: float = 1e-12,
) -> StructuralPath:
    if base_random_path.structural_family_id != "smooth_bounded_ar1":
        raise ContractError("exact-valid shift requires a smooth bounded base random path")
    k = base_random_path.action_locations.size
    ref = int(np.ceil(k / 2.0) - 1) if reference_action_index is None else int(reference_action_index)
    if not 0 <= ref < k:
        raise ContractError(f"reference_action_index={ref} outside [0,{k})")
    one_based = np.arange(1, k + 1, dtype=float)
    ref_one = float(ref + 1)
    denominator = float(np.max((one_based - ref_one) ** 2))
    g = 0.6 * (one_based - ref_one) ** 2 / denominator
    c = 0.1 * (1.0 + base_random_path.structural_state)
    loss = g[None, :] + c[:, None]
    best, margin = _best_mask_and_margin(loss, tie_tolerance)
    payload = {
        "seed": base_random_path.seed,
        "structural_family_id": "action_invariant_shift",
        "base_path_hash": base_random_path.path_hash,
        "reference_action_index": ref,
        "g_scale": 0.6,
        "c_scale": 0.1,
    }
    path_hash = _array_hash(
        base_random_path.source_rounds,
        base_random_path.latent_raw_state,
        base_random_path.structural_state,
        base_random_path.public_context,
        base_random_path.action_locations,
        loss,
        best,
        margin,
        payload=payload,
    )
    return StructuralPath(
        seed=base_random_path.seed,
        structural_family_id="action_invariant_shift",
        source_rounds=base_random_path.source_rounds.copy(),
        latent_raw_state=base_random_path.latent_raw_state.copy(),
        structural_state=base_random_path.structural_state.copy(),
        public_context=base_random_path.public_context.copy(),
        action_locations=base_random_path.action_locations.copy(),
        structural_loss_matrix=loss,
        structural_best_mask=best,
        structural_margin=margin,
        path_id=f"action_invariant_shift:{base_random_path.seed}:{path_hash[:16]}",
        path_hash=path_hash,
        parameter_payload=payload,
    )


def generate_systematic_misbinding_path(
    config: StructuralConfig,
    seed: int,
    block_length: int,
    left_action_index: int = 2,
    right_action_index: int = 7,
) -> StructuralPath:
    if block_length <= 0:
        raise ContractError("block_length must be positive")
    mu = action_locations(config.k_actions)
    if not (0 <= left_action_index < config.k_actions and 0 <= right_action_index < config.k_actions):
        raise ContractError("systematic preferred-action index outside action set")
    if left_action_index == right_action_index:
        raise ContractError("systematic preferred actions must differ")

    rounds = _source_rounds(config)
    n_source = rounds.size
    phase_rng = np.random.default_rng(int(seed) + 130_000)
    initial_side = int(phase_rng.integers(0, 2))
    phase_offset = int(phase_rng.integers(0, block_length))
    block_index = np.floor_divide(rounds + phase_offset, block_length)
    side = (block_index + initial_side) % 2
    state = np.where(side == 0, mu[left_action_index], mu[right_action_index]).astype(float)
    raw = np.arctanh(np.clip(state, -0.999999, 0.999999))
    context_rng = np.random.default_rng(int(seed) + 110_000)
    context = np.tanh(raw + context_rng.normal(0.0, config.context_noise_sd, size=n_source))
    loss = ((state[:, None] - mu[None, :]) / 2.0) ** 2
    best, margin = _best_mask_and_margin(loss, config.tie_tolerance)
    payload = {
        "seed": int(seed),
        "structural_family_id": "alternating_block_state",
        "block_length": int(block_length),
        "left_action_index": int(left_action_index),
        "right_action_index": int(right_action_index),
        "initial_side": initial_side,
        "phase_offset": phase_offset,
        "context_noise_sd": config.context_noise_sd,
    }
    path_hash = _array_hash(rounds, raw, state, context, mu, loss, best, margin, payload=payload)
    return StructuralPath(
        seed=int(seed),
        structural_family_id="alternating_block_state",
        source_rounds=rounds,
        latent_raw_state=raw,
        structural_state=state,
        public_context=context,
        action_locations=mu,
        structural_loss_matrix=loss,
        structural_best_mask=best,
        structural_margin=margin,
        path_id=f"alternating_block_state:{seed}:{path_hash[:16]}",
        path_hash=path_hash,
        parameter_payload=payload,
    )


def validate_structural_path(path: StructuralPath) -> dict[str, Any]:
    arrays = (
        path.source_rounds,
        path.latent_raw_state,
        path.structural_state,
        path.public_context,
        path.action_locations,
        path.structural_loss_matrix,
        path.structural_margin,
    )
    finite = all(np.all(np.isfinite(arr)) for arr in arrays)
    loss_min = float(np.min(path.structural_loss_matrix))
    loss_max = float(np.max(path.structural_loss_matrix))
    nonempty_optimal = bool(np.all(np.any(path.structural_best_mask, axis=1)))
    recomputed_best, recomputed_margin = _best_mask_and_margin(path.structural_loss_matrix, 1e-12)
    margin_reproducible = bool(
        np.array_equal(recomputed_best, path.structural_best_mask)
        and np.allclose(recomputed_margin, path.structural_margin, atol=1e-12, rtol=0.0)
    )
    report = {
        "finite_values": finite,
        "loss_min": loss_min,
        "loss_max": loss_max,
        "loss_in_unit_interval": bool(loss_min >= -1e-12 and loss_max <= 1.0 + 1e-12),
        "nonempty_optimal_set": nonempty_optimal,
        "margin_reproducible": margin_reproducible,
        "n_rounds": int(path.source_rounds.size),
        "k_actions": int(path.action_locations.size),
        "path_id": path.path_id,
        "path_hash": path.path_hash,
    }
    if not all(
        [finite, report["loss_in_unit_interval"], nonempty_optimal, margin_reproducible]
    ):
        raise ScientificInvariantError(f"Invalid structural path: {report}")
    return report


def structural_calibration_metrics(path: StructuralPath, prehistory_length: int) -> dict[str, float]:
    evaluation_slice = slice(prehistory_length, None)
    best_indices = np.argmin(path.structural_loss_matrix[evaluation_slice], axis=1)
    counts = np.bincount(best_indices, minlength=path.action_locations.size).astype(float)
    probabilities = counts / max(1.0, counts.sum())
    positive = probabilities[probabilities > 0]
    entropy = float(-np.sum(positive * np.log(positive)))
    normalized_entropy = float(entropy / np.log(path.action_locations.size))
    max_share = float(np.max(probabilities))
    switch_rate = float(np.mean(best_indices[1:] != best_indices[:-1])) if best_indices.size > 1 else 0.0
    spacing = 2.0 / (path.action_locations.size - 1)
    near_threshold = 0.1 * (spacing / 2.0) ** 2
    near_tie_share = float(np.mean(path.structural_margin[evaluation_slice] < near_threshold))
    return {
        "normalized_optimal_action_entropy": normalized_entropy,
        "max_optimal_action_share": max_share,
        "optimal_action_switch_rate": switch_rate,
        "near_tie_share": near_tie_share,
        "near_tie_threshold": float(near_threshold),
    }

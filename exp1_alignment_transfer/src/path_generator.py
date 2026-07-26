from __future__ import annotations

"""Assembly of frozen structural, delay, and learner-randomness paths."""

from dataclasses import dataclass
import hashlib
from typing import Any

import numpy as np

from config import DelayConfig, StructuralConfig
from src.artifact_io import hash_payload
from src.contracts import ContractError, validate_id
from src.delay_mechanisms import (
    DelayPath,
    generate_fixed_delay,
    generate_geometric_delay,
    generate_mixture_delay,
    generate_state_coupled_delay,
    generate_zero_delay,
    validate_delay_path,
)
from src.structural_process import (
    StructuralPath,
    generate_exact_valid_shift_path,
    generate_smooth_bounded_ar1_path,
    generate_systematic_misbinding_path,
    validate_structural_path,
)


@dataclass(frozen=True)
class SharedPathBundle:
    seed: int
    mechanism_id: str
    structural_path: StructuralPath
    delay_path: DelayPath
    learner_uniform_tape: np.ndarray
    learner_uniform_tape_id: str
    learner_uniform_tape_hash: str
    bundle_id: str
    bundle_hash: str


def _tape(seed: int, horizon: int) -> tuple[np.ndarray, str]:
    tape = np.random.default_rng(int(seed) + 300_000).random(int(horizon))
    h = hashlib.sha256(np.ascontiguousarray(tape).tobytes()).hexdigest()
    return tape, h


def build_shared_path_bundle(
    seed: int,
    mechanism_id: str,
    frozen_calibration: dict[str, Any],
    structural_config: StructuralConfig,
    delay_config: DelayConfig,
) -> SharedPathBundle:
    allowed = (
        "zero_delay",
        "exact_valid_shift",
        "geometric_delay",
        "mixture_delay",
        "state_coupled_delay",
        "systematic_misbinding",
    )
    validate_id(mechanism_id, allowed, "mechanism_id")

    base = generate_smooth_bounded_ar1_path(structural_config, int(seed))
    structural = base
    if mechanism_id == "exact_valid_shift":
        structural = generate_exact_valid_shift_path(base)
    elif mechanism_id == "systematic_misbinding":
        block_length = int(frozen_calibration["misbinding"]["selected_block_length"])
        structural = generate_systematic_misbinding_path(
            structural_config, int(seed), block_length=block_length
        )

    delay_params = frozen_calibration["delay"]
    if mechanism_id == "zero_delay":
        delay = generate_zero_delay(structural)
    elif mechanism_id in ("exact_valid_shift", "geometric_delay"):
        delay = generate_geometric_delay(
            structural,
            p=float(delay_params["geometric_probability"]),
            d_max=delay_config.d_max,
        )
    elif mechanism_id == "mixture_delay":
        delay = generate_mixture_delay(
            structural,
            mixture_weight_fast=float(delay_params["mixture_weight_fast"]),
            d_max=delay_config.d_max,
        )
    elif mechanism_id == "state_coupled_delay":
        delay = generate_state_coupled_delay(
            structural,
            intercept=float(delay_params["state_coupled_intercept"]),
            beta=delay_config.state_coupling_beta,
            d_max=delay_config.d_max,
        )
    elif mechanism_id == "systematic_misbinding":
        delay = generate_fixed_delay(structural, delay_config.fixed_delay)
    else:  # pragma: no cover - registry validation protects this
        raise ContractError(f"Unsupported mechanism {mechanism_id}")

    validate_structural_path(structural)
    validate_delay_path(delay, structural, delay_config.d_max)
    tape, tape_hash = _tape(int(seed), structural_config.horizon)
    payload = {
        "seed": int(seed),
        "mechanism_id": mechanism_id,
        "structural_path_hash": structural.path_hash,
        "delay_path_hash": delay.delay_path_hash,
        "learner_uniform_tape_hash": tape_hash,
    }
    bundle_hash = hash_payload(payload)
    return SharedPathBundle(
        seed=int(seed),
        mechanism_id=mechanism_id,
        structural_path=structural,
        delay_path=delay,
        learner_uniform_tape=tape,
        learner_uniform_tape_id=f"learner_uniform:{seed}:{tape_hash[:16]}",
        learner_uniform_tape_hash=tape_hash,
        bundle_id=f"bundle:{mechanism_id}:{seed}:{bundle_hash[:16]}",
        bundle_hash=bundle_hash,
    )

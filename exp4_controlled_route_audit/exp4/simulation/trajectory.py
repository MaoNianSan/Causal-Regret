"""Typed structural trajectory with independently derived random streams."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from exp4.configuration.parameters import SHARED_DGP
from exp4.simulation.action_space import construct_action_centers
from exp4.simulation.delay_process import generate_exact_mean_delays
from exp4.simulation.observation_proxy import (
    ObservationProxyBundle,
    construct_observation_proxy_bundle,
)
from exp4.simulation.state_process import generate_piecewise_states
from exp4.simulation.structural_loss import compute_structural_loss_map


STREAM_NAMES = (
    "state",
    "structural_feedback",
    "delay",
    "observation_proxy",
    "route_label",
    "audit_mcar",
    "audit_selective",
    "calibration_label",
    "control_noise",
    "control_permutation",
)


def stable_seed(module_id: str, task_id: int, stream_name: str) -> int:
    payload = f"{SHARED_DGP.root_seed}|{module_id}|{int(task_id)}|{stream_name}"
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little", signed=False)


def generator_for(module_id: str, task_id: int, stream_name: str) -> np.random.Generator:
    if stream_name not in STREAM_NAMES:
        raise KeyError(f"Unknown stream: {stream_name}")
    return np.random.default_rng(np.random.SeedSequence(stable_seed(module_id, task_id, stream_name)))


def hash_array(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(contiguous.dtype).encode("utf-8"))
    digest.update(str(contiguous.shape).encode("utf-8"))
    digest.update(contiguous.tobytes())
    return digest.hexdigest()


def hash_json(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _arrival_schedule(
    decision_horizon: int, delays: np.ndarray, clock_horizon: int
) -> tuple[np.ndarray, tuple[tuple[int, ...], ...]]:
    arrival_clocks = np.arange(decision_horizon, dtype=np.int64) + delays
    if int(np.max(arrival_clocks)) >= clock_horizon:
        raise RuntimeError("Extended clock does not cover every arrival")
    arrivals: list[list[int]] = [[] for _ in range(clock_horizon)]
    for source_round, arrival_clock in enumerate(arrival_clocks):
        arrivals[int(arrival_clock)].append(int(source_round))
    return arrival_clocks, tuple(tuple(values) for values in arrivals)


def _path_hashes(
    clock_states: np.ndarray,
    structural_loss_map: np.ndarray,
    realized_feedback: np.ndarray,
    delays: np.ndarray,
    observation_proxy: ObservationProxyBundle,
    route_label_uniforms: np.ndarray,
    audit_mcar: np.ndarray,
    audit_selective: np.ndarray,
    calibration_labels: np.ndarray,
) -> dict[str, str]:
    return {
        "state_path_hash": hash_array(clock_states),
        "structural_loss_map_hash": hash_array(structural_loss_map),
        "realized_feedback_hash": hash_array(realized_feedback),
        "delay_path_hash": hash_array(delays),
        "source_proxy_hash": hash_array(observation_proxy.source_proxy),
        "arrival_signature_noise_hash": hash_array(
            observation_proxy.arrival_signature_base_noise
        ),
        "route_label_uniform_hash": hash_array(route_label_uniforms),
        "audit_mcar_uniform_hash": hash_array(audit_mcar),
        "audit_selective_uniform_hash": hash_array(audit_selective),
        "calibration_label_uniform_hash": hash_array(calibration_labels),
    }


@dataclass(frozen=True)
class StructuralTrajectory:
    module_id: str
    task_id: int
    decision_horizon: int
    warmup: int
    clock_horizon: int
    action_centers: np.ndarray
    clock_states: np.ndarray
    structural_loss_map: np.ndarray
    realized_potential_feedback: np.ndarray
    transition_hazard: np.ndarray
    delays: np.ndarray
    arrival_clocks: np.ndarray
    arrivals_by_clock: tuple[tuple[int, ...], ...]
    observation_proxy: ObservationProxyBundle
    route_label_uniforms: np.ndarray
    audit_uniform_mcar: np.ndarray
    audit_uniform_selective: np.ndarray
    calibration_label_uniforms: np.ndarray
    stream_seeds: dict[str, int]
    trajectory_hash: str
    path_hashes: dict[str, str]

    @property
    def structural_states(self) -> np.ndarray:
        return self.clock_states[: self.decision_horizon]

    @property
    def evaluation_slice(self) -> slice:
        return slice(self.warmup, self.decision_horizon)

    @property
    def mean_delay(self) -> float:
        return float(np.mean(self.delays))

    def route_label_mask(self, rate: float) -> np.ndarray:
        return self.route_label_uniforms < float(rate)


def generate_structural_trajectory(
    module_id: str,
    task_id: int,
    decision_horizon: int,
    warmup: int,
) -> StructuralTrajectory:
    if decision_horizon <= warmup:
        raise ValueError("decision_horizon must exceed warmup")
    clock_horizon = int(decision_horizon + SHARED_DGP.maximum_candidate_delay)
    streams = {
        name: generator_for(module_id, task_id, name)
        for name in STREAM_NAMES
    }
    stream_seeds = {
        name: stable_seed(module_id, task_id, name)
        for name in STREAM_NAMES
    }
    action_centers = construct_action_centers(SHARED_DGP.num_actions)
    clock_states, clock_hazard = generate_piecewise_states(
        streams["state"], clock_horizon, action_centers
    )
    structural_states = clock_states[:decision_horizon]
    structural_loss_map = compute_structural_loss_map(structural_states, action_centers)
    realized_feedback = np.clip(
        structural_loss_map
        + streams["structural_feedback"].normal(
            0.0, SHARED_DGP.feedback_noise_sd, size=structural_loss_map.shape
        ),
        0.0,
        1.0,
    )
    transition_hazard = clock_hazard[:decision_horizon]
    delays = generate_exact_mean_delays(
        streams["delay"],
        transition_hazard,
        SHARED_DGP.delay_state_coupling,
        SHARED_DGP.target_mean_delay,
        SHARED_DGP.maximum_candidate_delay,
    )
    arrival_clocks, arrivals_by_clock = _arrival_schedule(
        decision_horizon, delays, clock_horizon
    )
    observation_proxy = construct_observation_proxy_bundle(
        structural_states, streams["observation_proxy"]
    )
    route_label_uniforms = streams["route_label"].random(decision_horizon)
    audit_mcar = streams["audit_mcar"].random(decision_horizon)
    audit_selective = streams["audit_selective"].random(decision_horizon)
    calibration_labels = streams["calibration_label"].random(decision_horizon)
    path_hashes = _path_hashes(
        clock_states,
        structural_loss_map,
        realized_feedback,
        delays,
        observation_proxy,
        route_label_uniforms,
        audit_mcar,
        audit_selective,
        calibration_labels,
    )
    trajectory_hash = hash_json(
        {
            "module_id": module_id,
            "task_id": task_id,
            "decision_horizon": decision_horizon,
            "warmup": warmup,
            "path_hashes": path_hashes,
        }
    )
    return StructuralTrajectory(
        module_id=module_id,
        task_id=int(task_id),
        decision_horizon=int(decision_horizon),
        warmup=int(warmup),
        clock_horizon=clock_horizon,
        action_centers=action_centers,
        clock_states=clock_states,
        structural_loss_map=structural_loss_map,
        realized_potential_feedback=realized_feedback.astype(np.float64),
        transition_hazard=transition_hazard,
        delays=delays,
        arrival_clocks=arrival_clocks,
        arrivals_by_clock=arrivals_by_clock,
        observation_proxy=observation_proxy,
        route_label_uniforms=route_label_uniforms,
        audit_uniform_mcar=audit_mcar,
        audit_uniform_selective=audit_selective,
        calibration_label_uniforms=calibration_labels,
        stream_seeds=stream_seeds,
        trajectory_hash=trajectory_hash,
        path_hashes=path_hashes,
    )


def save_trajectory(trajectory: StructuralTrajectory, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        module_id=np.array([trajectory.module_id]),
        task_id=np.array([trajectory.task_id], dtype=np.int64),
        decision_horizon=np.array([trajectory.decision_horizon], dtype=np.int64),
        warmup=np.array([trajectory.warmup], dtype=np.int64),
        clock_horizon=np.array([trajectory.clock_horizon], dtype=np.int64),
        action_centers=trajectory.action_centers,
        clock_states=trajectory.clock_states,
        structural_loss_map=trajectory.structural_loss_map,
        realized_potential_feedback=trajectory.realized_potential_feedback,
        transition_hazard=trajectory.transition_hazard,
        delays=trajectory.delays,
        arrival_clocks=trajectory.arrival_clocks,
        source_proxy=trajectory.observation_proxy.source_proxy,
        arrival_signature_base_noise=trajectory.observation_proxy.arrival_signature_base_noise,
        route_label_uniforms=trajectory.route_label_uniforms,
        audit_uniform_mcar=trajectory.audit_uniform_mcar,
        audit_uniform_selective=trajectory.audit_uniform_selective,
        calibration_label_uniforms=trajectory.calibration_label_uniforms,
        stream_seeds_json=np.array([json.dumps(trajectory.stream_seeds, sort_keys=True)]),
        trajectory_hash=np.array([trajectory.trajectory_hash]),
        path_hashes_json=np.array([json.dumps(trajectory.path_hashes, sort_keys=True)]),
    )

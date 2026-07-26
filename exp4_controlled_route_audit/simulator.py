"""Controlled structural process and delayed observation interface for Exp4."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

import config


def hash_array(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(contiguous.dtype).encode("utf-8"))
    digest.update(str(contiguous.shape).encode("utf-8"))
    digest.update(contiguous.tobytes())
    return digest.hexdigest()


def hash_json(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def construct_action_centers(num_actions: int) -> np.ndarray:
    grid = np.linspace(-1.45, 1.45, int(num_actions))
    return np.stack(
        [grid, 0.55 * np.sin(1.8 * grid), 0.35 * np.cos(1.3 * grid)], axis=1
    ).astype(np.float64)


def compute_structural_loss_map(states: np.ndarray, action_centers: np.ndarray) -> np.ndarray:
    states_2d = np.atleast_2d(states).astype(np.float64, copy=False)
    squared_distance = (
        (states_2d[:, None, :] - action_centers[None, :, :]) ** 2
    ).sum(axis=2)
    nearest_action = np.argmin(squared_distance, axis=1)
    regime_floor = np.where((nearest_action % 2) == 0, 0.035, 0.285)
    shape = 1.0 - np.exp(-squared_distance / 0.24)
    return np.clip(
        regime_floor[:, None] + (1.0 - regime_floor[:, None]) * shape,
        0.0,
        1.0,
    ).astype(np.float64)


def _generate_piecewise_states(
    rng: np.random.Generator,
    clock_horizon: int,
    action_centers: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate the legacy piecewise-stable exogenous state process."""
    state_dimension = action_centers.shape[1]
    states = np.zeros((clock_horizon, state_dimension), dtype=np.float64)
    coupling_score = np.zeros(clock_horizon, dtype=np.float64)
    clock = 0
    mode = int(rng.integers(0, len(action_centers)))
    while clock < clock_horizon:
        segment_length = int(rng.integers(26, 39))
        segment_end = min(clock_horizon, clock + segment_length)
        hazard_width = min(8, max(6, (segment_end - clock) // 4))
        for local_index, absolute_index in enumerate(range(clock, segment_end)):
            hazard = max(
                0.0,
                (local_index - ((segment_end - clock) - hazard_width) + 1)
                / hazard_width,
            )
            hazard = min(1.0, hazard)
            coupling_score[absolute_index] = hazard
            states[absolute_index] = (
                action_centers[mode]
                + np.array([0.0, 0.08 * hazard, -0.05 * hazard], dtype=float)
                + rng.normal(0.0, [0.055, 0.040, 0.035], size=state_dimension)
            )
        clock = segment_end
        alternatives = np.array(
            [action for action in range(len(action_centers)) if action != mode],
            dtype=int,
        )
        mode = int(rng.choice(alternatives))
    return np.clip(states, -1.8, 1.8), coupling_score


def _generate_exact_mean_delays(
    rng: np.random.Generator,
    coupling_score: np.ndarray,
    delay_state_coupling: float,
    target_mean_delay: int,
    maximum_candidate_delay: int,
) -> np.ndarray:
    """Generate integer delays with an exact realized mean for each trajectory."""
    number_of_rounds = len(coupling_score)
    standardized_score = (coupling_score - coupling_score.mean()) / (
        coupling_score.std() + 1e-12
    )
    jitter = rng.normal(0.0, 0.70, size=number_of_rounds)
    raw_delay = (
        target_mean_delay
        + float(delay_state_coupling) * 1.55 * standardized_score
        + jitter
    )
    delays = np.clip(
        np.rint(raw_delay).astype(int), 1, int(maximum_candidate_delay)
    )
    target_total = int(target_mean_delay) * number_of_rounds
    remaining = int(target_total - delays.sum())
    high_score_order = np.argsort(-standardized_score, kind="stable")
    low_score_order = np.argsort(standardized_score, kind="stable")
    if remaining > 0:
        cursor = 0
        while remaining > 0:
            index = int(high_score_order[cursor % number_of_rounds])
            if delays[index] < maximum_candidate_delay:
                delays[index] += 1
                remaining -= 1
            cursor += 1
    elif remaining < 0:
        cursor = 0
        while remaining < 0:
            index = int(low_score_order[cursor % number_of_rounds])
            if delays[index] > 1:
                delays[index] -= 1
                remaining += 1
            cursor += 1
    if int(delays.sum()) != target_total:
        raise RuntimeError("Delay calibration failed to attain the frozen mean delay.")
    return delays.astype(np.int64)


def _spawn_generators(root_seed: int) -> tuple[dict[str, np.random.Generator], dict[str, list[int]]]:
    root = np.random.SeedSequence(int(root_seed))
    children = root.spawn(len(config.STREAM_NAMES))
    generators: dict[str, np.random.Generator] = {}
    spawn_keys: dict[str, list[int]] = {}
    for name, child in zip(config.STREAM_NAMES, children, strict=True):
        generators[name] = np.random.default_rng(child)
        spawn_keys[name] = list(child.spawn_key)
    return generators, spawn_keys


@dataclass(frozen=True)
class StructuralTrajectory:
    seed_or_replication: int
    decision_horizon: int
    warmup_rounds: int
    clock_horizon: int
    action_centers: np.ndarray
    clock_states: np.ndarray
    structural_loss_map: np.ndarray
    realized_potential_feedback: np.ndarray
    delays: np.ndarray
    arrival_clocks: np.ndarray
    arrivals_by_clock: tuple[tuple[int, ...], ...]
    context_proxy: np.ndarray
    attribution_proxy_base_noise: np.ndarray
    route_label_uniforms: np.ndarray
    audit_uniform_mcar: np.ndarray
    audit_uniform_biased: np.ndarray
    coupling_score: np.ndarray
    stream_spawn_keys: dict[str, list[int]]
    path_id: str
    path_hashes: dict[str, str]

    @property
    def structural_states(self) -> np.ndarray:
        return self.clock_states[: self.decision_horizon]

    @property
    def mean_delay(self) -> float:
        return float(np.mean(self.delays))

    @property
    def evaluation_slice(self) -> slice:
        return slice(self.warmup_rounds, self.decision_horizon)

    def attribution_proxy(self, attribution_proxy_noise_sd: float) -> np.ndarray:
        return self.clock_states + float(attribution_proxy_noise_sd) * self.attribution_proxy_base_noise

    def route_label_mask(self, route_label_rate: float) -> np.ndarray:
        return self.route_label_uniforms < float(route_label_rate)

    def context_ids(self) -> np.ndarray:
        squared_distance = (
            (self.context_proxy[:, None, :] - self.action_centers[None, :, :]) ** 2
        ).sum(axis=2)
        return np.argmin(squared_distance, axis=1).astype(np.int64)


def generate_structural_trajectory(
    seed_or_replication: int,
    decision_horizon: int,
    warmup_rounds: int,
) -> StructuralTrajectory:
    """Generate one complete shared structural and observation path."""
    parameters = config.PARAMETERS
    if decision_horizon <= warmup_rounds:
        raise ValueError("decision_horizon must exceed warmup_rounds")
    clock_horizon = decision_horizon + parameters.maximum_candidate_delay
    generators, spawn_keys = _spawn_generators(seed_or_replication)
    action_centers = construct_action_centers(parameters.num_actions)
    clock_states, coupling_score_clock = _generate_piecewise_states(
        generators["state_stream"], clock_horizon, action_centers
    )
    structural_states = clock_states[:decision_horizon]
    structural_loss_map = compute_structural_loss_map(structural_states, action_centers)
    feedback_noise = generators["structural_feedback_stream"].normal(
        0.0, 0.009, size=structural_loss_map.shape
    )
    realized_potential_feedback = np.clip(
        structural_loss_map + feedback_noise, 0.0, 1.0
    ).astype(np.float64)
    coupling_score = (coupling_score_clock[:decision_horizon] > 0.0).astype(float)
    delays = _generate_exact_mean_delays(
        generators["delay_stream"],
        coupling_score,
        parameters.delay_state_coupling,
        parameters.target_mean_delay,
        parameters.maximum_candidate_delay,
    )
    arrival_clocks = np.arange(decision_horizon, dtype=np.int64) + delays
    if int(arrival_clocks.max()) >= clock_horizon:
        raise RuntimeError("Extended observation clock does not cover every source arrival.")
    arrivals: list[list[int]] = [[] for _ in range(clock_horizon)]
    for source_round, arrival_clock in enumerate(arrival_clocks):
        arrivals[int(arrival_clock)].append(int(source_round))
    context_noise = generators["context_proxy_stream"].normal(
        size=clock_states.shape
    )
    context_proxy = (
        clock_states + parameters.context_proxy_noise_sd * context_noise
    ).astype(np.float64)
    attribution_proxy_base_noise = generators["attribution_proxy_stream"].normal(
        size=clock_states.shape
    ).astype(np.float64)
    route_label_uniforms = generators["route_label_stream"].random(decision_horizon)
    audit_uniform_mcar = generators["audit_mcar_stream"].random(decision_horizon)
    audit_uniform_biased = generators["audit_biased_stream"].random(decision_horizon)

    path_hashes = {
        "state_path_hash": hash_array(clock_states),
        "structural_loss_map_hash": hash_array(structural_loss_map),
        "realized_feedback_hash": hash_array(realized_potential_feedback),
        "delay_path_hash": hash_array(delays),
        "context_proxy_hash": hash_array(context_proxy),
        "attribution_proxy_base_noise_hash": hash_array(attribution_proxy_base_noise),
        "route_label_uniform_hash": hash_array(route_label_uniforms),
        "audit_mcar_uniform_hash": hash_array(audit_uniform_mcar),
        "audit_biased_uniform_hash": hash_array(audit_uniform_biased),
    }
    path_id = hash_json(
        {
            "seed_or_replication": int(seed_or_replication),
            "decision_horizon": int(decision_horizon),
            "warmup_rounds": int(warmup_rounds),
            "hashes": path_hashes,
        }
    )[:20]
    return StructuralTrajectory(
        seed_or_replication=int(seed_or_replication),
        decision_horizon=int(decision_horizon),
        warmup_rounds=int(warmup_rounds),
        clock_horizon=int(clock_horizon),
        action_centers=action_centers,
        clock_states=clock_states.astype(np.float64),
        structural_loss_map=structural_loss_map,
        realized_potential_feedback=realized_potential_feedback,
        delays=delays,
        arrival_clocks=arrival_clocks,
        arrivals_by_clock=tuple(tuple(values) for values in arrivals),
        context_proxy=context_proxy,
        attribution_proxy_base_noise=attribution_proxy_base_noise,
        route_label_uniforms=route_label_uniforms.astype(np.float64),
        audit_uniform_mcar=audit_uniform_mcar.astype(np.float64),
        audit_uniform_biased=audit_uniform_biased.astype(np.float64),
        coupling_score=coupling_score.astype(np.float64),
        stream_spawn_keys=spawn_keys,
        path_id=path_id,
        path_hashes=path_hashes,
    )


def save_structural_trajectory(trajectory: StructuralTrajectory, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        seed_or_replication=np.array([trajectory.seed_or_replication], dtype=np.int64),
        decision_horizon=np.array([trajectory.decision_horizon], dtype=np.int64),
        warmup_rounds=np.array([trajectory.warmup_rounds], dtype=np.int64),
        clock_horizon=np.array([trajectory.clock_horizon], dtype=np.int64),
        action_centers=trajectory.action_centers,
        clock_states=trajectory.clock_states,
        structural_loss_map=trajectory.structural_loss_map,
        realized_potential_feedback=trajectory.realized_potential_feedback,
        delays=trajectory.delays,
        arrival_clocks=trajectory.arrival_clocks,
        context_proxy=trajectory.context_proxy,
        attribution_proxy_base_noise=trajectory.attribution_proxy_base_noise,
        route_label_uniforms=trajectory.route_label_uniforms,
        audit_uniform_mcar=trajectory.audit_uniform_mcar,
        audit_uniform_biased=trajectory.audit_uniform_biased,
        coupling_score=trajectory.coupling_score,
        path_id=np.array([trajectory.path_id]),
        path_hashes_json=np.array([json.dumps(trajectory.path_hashes, sort_keys=True)]),
        stream_spawn_keys_json=np.array(
            [json.dumps(trajectory.stream_spawn_keys, sort_keys=True)]
        ),
    )


def trajectory_manifest_record(
    trajectory: StructuralTrajectory, output_path: Path, run_dir: Path
) -> dict[str, Any]:
    return {
        "seed_or_replication": trajectory.seed_or_replication,
        "path_id": trajectory.path_id,
        "trajectory_file": output_path.relative_to(run_dir).as_posix(),
        "decision_horizon": trajectory.decision_horizon,
        "warmup_rounds": trajectory.warmup_rounds,
        "clock_horizon": trajectory.clock_horizon,
        "mean_delay": trajectory.mean_delay,
        **trajectory.path_hashes,
        "stream_spawn_keys": json.dumps(trajectory.stream_spawn_keys, sort_keys=True),
    }

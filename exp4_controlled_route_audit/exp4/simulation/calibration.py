"""Independent calibration of proxy bandwidth and the empirical delay prior."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from exp4.configuration.parameters import CALIBRATION, MODULE_A, SHARED_DGP
from exp4.simulation.trajectory import generate_structural_trajectory


@dataclass(frozen=True)
class ProxyRouteCalibration:
    calibration_seed_ids: tuple[int, ...]
    kernel_bandwidth: float
    delay_prior_smoothing: float
    delay_support: np.ndarray
    delay_probabilities: np.ndarray
    source_code_hash: str
    config_hash: str
    calibration_hash: str

    def as_json(self) -> dict[str, object]:
        return {
            "calibration_seed_ids": list(self.calibration_seed_ids),
            "kernel_bandwidth": self.kernel_bandwidth,
            "delay_prior_smoothing": self.delay_prior_smoothing,
            "delay_support": self.delay_support.tolist(),
            "delay_probabilities": self.delay_probabilities.tolist(),
            "source_code_hash": self.source_code_hash,
            "config_hash": self.config_hash,
            "calibration_hash": self.calibration_hash,
            "proxy_calibration_noise_sd": CALIBRATION.proxy_calibration_noise_sd,
            "evaluation_seed_overlap": False,
        }


def load_proxy_route_calibration(path: Path) -> ProxyRouteCalibration:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ProxyRouteCalibration(
        calibration_seed_ids=tuple(int(value) for value in payload["calibration_seed_ids"]),
        kernel_bandwidth=float(payload["kernel_bandwidth"]),
        delay_prior_smoothing=float(payload["delay_prior_smoothing"]),
        delay_support=np.asarray(payload["delay_support"], dtype=np.int64),
        delay_probabilities=np.asarray(payload["delay_probabilities"], dtype=np.float64),
        source_code_hash=str(payload["source_code_hash"]),
        config_hash=str(payload["config_hash"]),
        calibration_hash=str(payload["calibration_hash"]),
    )


def candidate_source_indices(arrival_clock: int, decision_horizon: int) -> np.ndarray:
    lower = max(0, int(arrival_clock) - SHARED_DGP.maximum_candidate_delay)
    upper = min(int(arrival_clock), int(decision_horizon))
    candidates = np.arange(lower, upper, dtype=np.int64)
    if candidates.size == 0:
        raise RuntimeError(f"No historical candidates at arrival clock {arrival_clock}")
    return candidates


def calibrate_proxy_route(source_code_hash: str, config_hash: str) -> tuple[
    ProxyRouteCalibration, pd.DataFrame, pd.DataFrame
]:
    distances: list[np.ndarray] = []
    delay_counts = np.zeros(SHARED_DGP.maximum_candidate_delay, dtype=np.int64)
    for calibration_seed in CALIBRATION.calibration_seeds:
        trajectory = generate_structural_trajectory(
            "proxy_calibration",
            calibration_seed,
            MODULE_A.horizon,
            MODULE_A.warmup,
        )
        signatures = trajectory.observation_proxy.arrival_signature(
            CALIBRATION.proxy_calibration_noise_sd
        )
        for source_round, arrival_clock in enumerate(trajectory.arrival_clocks):
            candidates = candidate_source_indices(arrival_clock, trajectory.decision_horizon)
            differences = trajectory.observation_proxy.source_proxy[candidates] - signatures[source_round]
            distances.append(np.linalg.norm(differences, axis=1))
        delay_counts += np.bincount(
            trajectory.delays - 1,
            minlength=SHARED_DGP.maximum_candidate_delay,
        )[: SHARED_DGP.maximum_candidate_delay]
    distance_values = np.concatenate(distances)
    finite_distances = distance_values[np.isfinite(distance_values)]
    kernel_bandwidth = float(np.median(finite_distances))
    if not np.isfinite(kernel_bandwidth) or kernel_bandwidth <= 0.0:
        raise RuntimeError("Proxy calibration produced an invalid kernel bandwidth")
    smoothing = float(CALIBRATION.delay_prior_smoothing)
    delay_probabilities = (delay_counts + smoothing) / float(
        np.sum(delay_counts) + smoothing * len(delay_counts)
    )
    delay_support = np.arange(1, len(delay_counts) + 1, dtype=np.int64)
    payload = {
        "calibration_seed_ids": list(CALIBRATION.calibration_seeds),
        "kernel_bandwidth": kernel_bandwidth,
        "delay_prior_smoothing": smoothing,
        "delay_support": delay_support.tolist(),
        "delay_probabilities": delay_probabilities.tolist(),
        "source_code_hash": source_code_hash,
        "config_hash": config_hash,
    }
    calibration_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    artifact = ProxyRouteCalibration(
        calibration_seed_ids=CALIBRATION.calibration_seeds,
        kernel_bandwidth=kernel_bandwidth,
        delay_prior_smoothing=smoothing,
        delay_support=delay_support,
        delay_probabilities=delay_probabilities,
        source_code_hash=source_code_hash,
        config_hash=config_hash,
        calibration_hash=calibration_hash,
    )
    delay_frame = pd.DataFrame(
        {
            "delay": delay_support,
            "count": delay_counts,
            "probability": delay_probabilities,
        }
    )
    quantiles = (0.0, 0.10, 0.25, 0.50, 0.75, 0.90, 1.0)
    distance_frame = pd.DataFrame(
        {
            "quantile": quantiles,
            "proxy_distance": np.quantile(finite_distances, quantiles),
            "candidate_distance_count": len(finite_distances),
            "calibration_seed_count": len(CALIBRATION.calibration_seeds),
        }
    )
    return artifact, delay_frame, distance_frame

"""Observable candidate proxies and arrival-side source signatures."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ObservationProxyBundle:
    source_proxy: np.ndarray
    arrival_signature_base_noise: np.ndarray

    def arrival_signature(self, noise_sd: float) -> np.ndarray:
        return self.source_proxy + float(noise_sd) * self.arrival_signature_base_noise


def construct_observation_proxy_bundle(
    structural_states: np.ndarray, rng: np.random.Generator
) -> ObservationProxyBundle:
    source_proxy = structural_states.astype(np.float64, copy=True)
    base_noise = rng.normal(size=source_proxy.shape).astype(np.float64)
    return ObservationProxyBundle(source_proxy, base_noise)

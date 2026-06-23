from __future__ import annotations

"""Contextual delayed-feedback environment for EXP1.

Every learner observes the same noisy decision-time context X_t.  Regret is
computed against the context-information oracle rather than a full-state oracle,
so the estimand isolates delay/attribution distortion from irreducible partial
observability.
"""

from typing import Any

import numpy as np

from src.delay import (
    CONTEXT_NOISE_SD,
    RHO,
    STATE_NOISE_SD,
    ScenarioTrace,
    action_dependent_delay,
)


class ToyDelayedEnv:
    def __init__(self, T: int, K: int, D_max: int, trace: ScenarioTrace, env_seed: int = 0):
        self.T = int(T)
        self.K = int(K)
        self.D_max = int(D_max)
        self.trace = trace
        self.env_seed = int(env_seed)
        self.mu = np.linspace(-1.0, 1.0, self.K).astype(float)
        self.context_noise_sd = float(CONTEXT_NOISE_SD)
        self.reset(env_seed=self.env_seed)

    def reset(self, env_seed: int = 0):
        self.env_seed = int(env_seed)
        self.delay_rng = np.random.default_rng(self.env_seed + 300_000)
        self.queue = [[] for _ in range(self.T + self.D_max + 5)]
        self._generated = 0
        self._censored = 0
        self._uncensored = 0
        self._clock = -1
        self.S = float(self.trace.states[0]) if self.T else 0.0
        self.X = float(self.trace.contexts[0]) if self.T else 0.0

    def step_state(self) -> float:
        self._clock += 1
        if self._clock >= self.T:
            raise IndexError("environment advanced beyond horizon")
        self.S = float(self.trace.states[self._clock])
        self.X = float(self.trace.contexts[self._clock])
        return self.S

    def context_at(self, t: int) -> float:
        return float(self.trace.contexts[int(t)])

    def proxy_observation_at(self, t: int) -> float:
        return float(self.trace.proxy_observations[int(t)])

    def loss_true(self, a: int, s: float) -> float:
        delta = float(s) - float(self.mu[int(a)])
        return float(delta * delta)

    def loss_vector(self, s: float) -> np.ndarray:
        return ((float(s) - self.mu) ** 2).astype(float)

    def _posterior_moments(self, x: float) -> tuple[float, float]:
        if self.trace.state_process == "static":
            return float(self.trace.fixed_state or 0.0), 0.0
        state_var = (STATE_NOISE_SD**2) / max(1e-9, 1.0 - RHO**2)
        noise_var = self.context_noise_sd**2
        gain = state_var / (state_var + noise_var)
        mean = gain * float(x)
        var = state_var * (1.0 - gain)
        return float(mean), float(var)

    def conditional_risk_vector(self, x: float) -> np.ndarray:
        mean, var = self._posterior_moments(float(x))
        return (var + (mean - self.mu) ** 2).astype(float)

    def optimal_action_from_context(self, x: float) -> int:
        return int(np.argmin(self.conditional_risk_vector(float(x))))

    def conditional_regret_at_t(self, a: int, x: float) -> float:
        risks = self.conditional_risk_vector(float(x))
        return float(risks[int(a)] - np.min(risks))

    # Alias retained for older plotting/runner expectations.
    def regret_at_t(self, a: int, s_or_x: float) -> float:
        return self.conditional_regret_at_t(a, s_or_x)

    def step_schedule(self, a_t: int, t: int) -> dict[str, Any]:
        a_t = int(a_t)
        t = int(t)
        s_t = float(self.trace.states[t])
        x_t = float(self.trace.contexts[t])
        loss = self.loss_true(a_t, s_t)
        source_optimal_action = self.optimal_action_from_context(x_t)
        if self.trace.policy_dependent_delay:
            d, hazard = action_dependent_delay(self.trace, t, a_t, self.delay_rng)
        else:
            d = int(np.asarray(self.trace.delays, dtype=int)[t])
            hazard = float(np.asarray(self.trace.delay_probabilities, dtype=float)[t])
        arrival_t = int(t + d)
        self._generated += 1
        reason = "none"
        if d > self.D_max:
            reason = "delay_exceeds_Dmax"
        elif arrival_t >= self.T:
            reason = "arrival_out_of_horizon"
        censored = reason != "none"
        row: dict[str, Any] = {
            "source_t": t,
            "source_state": s_t,
            "source_context": x_t,
            "source_action": a_t,
            "source_loss": loss,
            "source_optimal_action": int(source_optimal_action),
            "delay_tau": int(d),
            "delay_hazard": float(hazard),
            "arrival_t": arrival_t,
            "is_censored": bool(censored),
            "censor_reason": reason,
        }
        if censored:
            self._censored += 1
            return row
        self._uncensored += 1
        self.queue[arrival_t].append(
            {
                "loss": loss,
                "src_t": t,
                "src_a": a_t,
                "src_s": s_t,
                "src_x": x_t,
                "src_optimal_action": int(source_optimal_action),
                "delay_tau": int(d),
                "arrival_t": arrival_t,
            }
        )
        return row

    def pop_arrivals(self, t: int):
        arr = self.queue[int(t)]
        self.queue[int(t)] = []
        return arr

    def censor_ratio(self) -> float:
        return float(self._censored / max(1, self._generated))

from __future__ import annotations

"""Delay mechanisms and pre-generated, policy-independent scenario traces.

The EXP1 primary comparison is intentionally restricted to mechanisms whose delay
path can be fixed before any learner acts.  This makes the state path, observed
context path, censoring rule, and realised delay sequence identical across
methods.  Action-dependent delay is retained only as an explicitly marked
policy-dependent stress test.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np


RHO = 0.98
STATE_NOISE_SD = 0.25
STATE_CLIP = 2.5
CONTEXT_NOISE_SD = 0.35
PROXY_EXTRA_NOISE_DEFAULT = 0.0
TARGET_OBSERVED_DELAY = 15.0


@dataclass(frozen=True)
class ScenarioTrace:
    """A shared exogenous path for one seed × delay setting.

    ``delays`` is populated for policy-independent scenarios.  For the
    action-dependent stress test it is ``None`` and the environment samples
    policy-specific delays from a separate, clearly labelled mechanism.
    """

    setting: str
    seed: int
    states: np.ndarray
    contexts: np.ndarray
    proxy_observations: np.ndarray
    delays: np.ndarray | None
    delay_probabilities: np.ndarray | None
    delay_cfg: dict[str, Any]
    observed_mean_delay: float
    observed_count: int
    policy_dependent_delay: bool
    calibration_target: float | None
    calibration_metric: str
    state_process: str
    fixed_state: float | None


def sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    arr = np.asarray(x, dtype=float)
    out = np.empty_like(arr, dtype=float)
    pos = arr >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-arr[pos]))
    z = np.exp(arr[~pos])
    out[~pos] = z / (1.0 + z)
    if np.ndim(x) == 0:
        return float(out.item())
    return out


def _geom0_from_uniform(u: np.ndarray, p: np.ndarray | float) -> np.ndarray:
    """Inverse-CDF draw for Geom(p)-1 using fixed uniforms.

    Fixed uniforms make calibration deterministic and make realised paths common
    across learners.  The output is non-negative integer delay.
    """

    pp = np.clip(np.asarray(p, dtype=float), 1e-6, 1.0 - 1e-8)
    uu = np.clip(np.asarray(u, dtype=float), 1e-12, 1.0 - 1e-12)
    # P(D <= k) = 1 - (1-p)^(k+1).
    return np.floor(np.log1p(-uu) / np.log1p(-pp)).astype(int)


def _observed_delay_mean(delays: np.ndarray, T: int, D_max: int) -> tuple[float, int]:
    t = np.arange(int(T), dtype=int)
    d = np.asarray(delays, dtype=int)
    observed = (d <= int(D_max)) & (t + d < int(T))
    if not np.any(observed):
        return float("nan"), 0
    return float(np.mean(d[observed])), int(np.sum(observed))


def _calibrate_monotone(
    evaluate_mean,
    target: float,
    lo: float,
    hi: float,
    decreasing: bool,
    iterations: int = 56,
) -> float:
    """Binary-search a scalar to match the *observed* finite-horizon mean."""

    target = float(target)
    for _ in range(int(iterations)):
        mid = 0.5 * (lo + hi)
        value = float(evaluate_mean(mid))
        if not np.isfinite(value):
            lo = mid
            continue
        # For decreasing functions, a value above target requires increasing x.
        if decreasing:
            if value > target:
                lo = mid
            else:
                hi = mid
        else:
            if value < target:
                lo = mid
            else:
                hi = mid
    return float(0.5 * (lo + hi))


def _simulate_states_and_contexts(
    T: int,
    seed: int,
    state_process: str,
    fixed_state: float | None,
    context_noise_sd: float,
    proxy_extra_noise_sd: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng_state = np.random.default_rng(int(seed) + 100_000)
    rng_context = np.random.default_rng(int(seed) + 110_000)
    rng_proxy = np.random.default_rng(int(seed) + 120_000)
    T = int(T)
    if state_process == "static":
        value = float(0.0 if fixed_state is None else fixed_state)
        states = np.full(T, value, dtype=float)
    else:
        states = np.zeros(T, dtype=float)
        s = 0.0
        for t in range(T):
            # No clipping: this is the exact Gaussian AR(1) law used by the
            # conditional-risk oracle and the EM observable-state integration.
            s = float(RHO * s + rng_state.normal(0.0, STATE_NOISE_SD))
            states[t] = s
    contexts = states + rng_context.normal(0.0, float(context_noise_sd), size=T)
    proxy_obs = contexts + rng_proxy.normal(0.0, float(proxy_extra_noise_sd), size=T)
    return states.astype(float), contexts.astype(float), proxy_obs.astype(float)


def scenario_definitions() -> dict[str, dict[str, Any]]:
    """EXP1 scenarios.

    The three ``*_matched_15`` primary mechanisms are calibrated against the
    same realised, finite-horizon and uncensored delay target.  The final
    action-dependent setting is deliberately excluded from that matched claim.
    """

    return {
        "zero_static": {
            "delay_name": "zero",
            "state_process": "static",
            "fixed_state": 0.0,
            "policy_dependent_delay": False,
            "target_observed_delay": 0.0,
            "context_noise_sd": 0.0,
            "proxy_extra_noise_sd": 0.0,
        },
        "aligned_static_delay_15": {
            "delay_name": "fixed",
            "delay_value": 15,
            "state_process": "static",
            "fixed_state": 0.0,
            "policy_dependent_delay": False,
            "target_observed_delay": 15.0,
            "context_noise_sd": 0.0,
            "proxy_extra_noise_sd": 0.0,
        },
        "geometric_matched_15": {
            "delay_name": "geometric",
            "state_process": "ar1",
            "policy_dependent_delay": False,
            "target_observed_delay": TARGET_OBSERVED_DELAY,
            "context_noise_sd": CONTEXT_NOISE_SD,
            "proxy_extra_noise_sd": 0.0,
        },
        "mixture_matched_15": {
            "delay_name": "mixture",
            "p_fast": 1.0 / 3.0,
            "p_slow": 1.0 / 31.0,
            "state_process": "ar1",
            "policy_dependent_delay": False,
            "target_observed_delay": TARGET_OBSERVED_DELAY,
            "context_noise_sd": CONTEXT_NOISE_SD,
            "proxy_extra_noise_sd": 0.0,
        },
        "state_structural_matched_15": {
            "delay_name": "state_structural",
            "beta": 1.0,
            "state_process": "ar1",
            "policy_dependent_delay": False,
            "target_observed_delay": TARGET_OBSERVED_DELAY,
            "context_noise_sd": CONTEXT_NOISE_SD,
            "proxy_extra_noise_sd": 0.0,
        },
        "proxy_good_matched_15": {
            "delay_name": "state_structural",
            "beta": 1.0,
            "state_process": "ar1",
            "policy_dependent_delay": False,
            "target_observed_delay": TARGET_OBSERVED_DELAY,
            "context_noise_sd": CONTEXT_NOISE_SD,
            "proxy_extra_noise_sd": 0.20,
            "proxy_quality": "high",
        },
        "proxy_bad_matched_15": {
            "delay_name": "state_structural",
            "beta": 1.0,
            "state_process": "ar1",
            "policy_dependent_delay": False,
            "target_observed_delay": TARGET_OBSERVED_DELAY,
            "context_noise_sd": CONTEXT_NOISE_SD,
            "proxy_extra_noise_sd": 4.00,
            "proxy_quality": "low",
        },
        "action_structural_stress": {
            "delay_name": "action_structural",
            "beta": 1.0,
            "alpha_std": 0.65,
            "state_process": "ar1",
            "policy_dependent_delay": True,
            "target_observed_delay": TARGET_OBSERVED_DELAY,
            "context_noise_sd": CONTEXT_NOISE_SD,
            "proxy_extra_noise_sd": 0.0,
        },
    }


def _build_policy_independent_delays(
    cfg: dict[str, Any], states: np.ndarray, T: int, D_max: int, seed: int
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    rng = np.random.default_rng(int(seed) + 200_000)
    u_len = rng.random(int(T))
    u_mix = rng.random(int(T))
    name = str(cfg["delay_name"])
    target = float(cfg.get("target_observed_delay", 0.0))

    if name == "zero":
        delays = np.zeros(T, dtype=int)
        probs = np.ones(T, dtype=float)
        return delays, probs, {"name": name}
    if name == "fixed":
        d = int(cfg["delay_value"])
        delays = np.full(T, d, dtype=int)
        probs = np.ones(T, dtype=float)
        return delays, probs, {"name": name, "delay_value": d}
    if name == "geometric":
        def draw(p: float) -> np.ndarray:
            return _geom0_from_uniform(u_len, p)

        p = _calibrate_monotone(
            lambda z: _observed_delay_mean(draw(z), T, D_max)[0],
            target=target,
            lo=1e-4,
            hi=0.95,
            decreasing=True,
        )
        delays = draw(p)
        return delays, np.full(T, p, dtype=float), {"name": name, "p": float(p)}
    if name == "mixture":
        p_fast = float(cfg["p_fast"])
        p_slow = float(cfg["p_slow"])
        d_fast = _geom0_from_uniform(u_len, p_fast)
        d_slow = _geom0_from_uniform(u_len, p_slow)

        def draw(w: float) -> np.ndarray:
            return np.where(u_mix < float(w), d_fast, d_slow).astype(int)

        w = _calibrate_monotone(
            lambda z: _observed_delay_mean(draw(z), T, D_max)[0],
            target=target,
            lo=0.0,
            hi=1.0,
            decreasing=True,
        )
        delays = draw(w)
        p_effective = w * p_fast + (1.0 - w) * p_slow
        return delays, np.full(T, p_effective, dtype=float), {
            "name": name,
            "w": float(w),
            "p_fast": p_fast,
            "p_slow": p_slow,
        }
    if name == "state_structural":
        beta = float(cfg["beta"])

        def draw(c: float) -> tuple[np.ndarray, np.ndarray]:
            p = np.asarray(sigmoid(beta * states + float(c)), dtype=float)
            return _geom0_from_uniform(u_len, p), p

        c = _calibrate_monotone(
            lambda z: _observed_delay_mean(draw(z)[0], T, D_max)[0],
            target=target,
            lo=-10.0,
            hi=8.0,
            decreasing=True,
        )
        delays, probs = draw(c)
        return delays, probs, {"name": name, "beta": beta, "c": float(c)}
    raise ValueError(f"Unsupported policy-independent delay: {name}")


def build_scenario_trace(setting: str, seed: int, T: int, D_max: int, K: int) -> ScenarioTrace:
    definitions = scenario_definitions()
    if setting not in definitions:
        raise KeyError(f"Unknown scenario setting: {setting}")
    cfg = dict(definitions[setting])
    states, contexts, proxy_obs = _simulate_states_and_contexts(
        T=T,
        seed=int(seed),
        state_process=str(cfg.get("state_process", "ar1")),
        fixed_state=cfg.get("fixed_state"),
        context_noise_sd=float(cfg.get("context_noise_sd", CONTEXT_NOISE_SD)),
        proxy_extra_noise_sd=float(cfg.get("proxy_extra_noise_sd", PROXY_EXTRA_NOISE_DEFAULT)),
    )

    policy_dependent = bool(cfg.get("policy_dependent_delay", False))
    if policy_dependent:
        # Reference calibration uses an exogenous uniform action stream only.
        # It is metadata, not a claim that each learner has the same realised
        # mean delay under this stress test.
        rng = np.random.default_rng(int(seed) + 200_000)
        u_len = rng.random(int(T))
        reference_actions = rng.integers(0, int(K), size=int(T))
        alpha_rng = np.random.default_rng(int(seed) + 210_000)
        alpha = alpha_rng.normal(0.0, float(cfg.get("alpha_std", 0.65)), size=int(K))
        beta = float(cfg.get("beta", 1.0))
        target = float(cfg.get("target_observed_delay", TARGET_OBSERVED_DELAY))

        def ref_draw(c: float) -> np.ndarray:
            p = np.asarray(sigmoid(alpha[reference_actions] + beta * states + float(c)), dtype=float)
            return _geom0_from_uniform(u_len, p)

        c = _calibrate_monotone(
            lambda z: _observed_delay_mean(ref_draw(z), T, D_max)[0],
            target=target,
            lo=-10.0,
            hi=8.0,
            decreasing=True,
        )
        ref_delays = ref_draw(c)
        ref_mean, ref_n = _observed_delay_mean(ref_delays, T, D_max)
        delay_cfg = {
            "name": "action_structural",
            "beta": beta,
            "c": float(c),
            "alpha": alpha.astype(float),
            "u_len_seed": int(seed) + 200_000,
        }
        return ScenarioTrace(
            setting=setting,
            seed=int(seed),
            states=states,
            contexts=contexts,
            proxy_observations=proxy_obs,
            delays=None,
            delay_probabilities=None,
            delay_cfg=delay_cfg,
            observed_mean_delay=float(ref_mean),
            observed_count=int(ref_n),
            policy_dependent_delay=True,
            calibration_target=target,
            calibration_metric="reference-policy observed uncensored mean delay",
            state_process=str(cfg.get("state_process", "ar1")),
            fixed_state=cfg.get("fixed_state"),
        )

    delays, probs, delay_cfg = _build_policy_independent_delays(cfg, states, T, D_max, seed)
    observed_mean, observed_n = _observed_delay_mean(delays, T, D_max)
    return ScenarioTrace(
        setting=setting,
        seed=int(seed),
        states=states,
        contexts=contexts,
        proxy_observations=proxy_obs,
        delays=delays.astype(int),
        delay_probabilities=probs.astype(float),
        delay_cfg=delay_cfg,
        observed_mean_delay=float(observed_mean),
        observed_count=int(observed_n),
        policy_dependent_delay=False,
        calibration_target=float(cfg.get("target_observed_delay", observed_mean)),
        calibration_metric="realised uncensored finite-horizon mean delay",
        state_process=str(cfg.get("state_process", "ar1")),
        fixed_state=cfg.get("fixed_state"),
    )


def action_dependent_delay(trace: ScenarioTrace, t: int, action: int, rng: np.random.Generator) -> tuple[int, float]:
    """Sample a delay for the explicitly policy-dependent stress test."""

    if not trace.policy_dependent_delay:
        raise ValueError("action_dependent_delay called for a shared-path trace")
    cfg = trace.delay_cfg
    alpha = np.asarray(cfg["alpha"], dtype=float)
    p = float(sigmoid(float(alpha[int(action)]) + float(cfg["beta"]) * float(trace.states[int(t)]) + float(cfg["c"])))
    p = float(np.clip(p, 1e-6, 1.0 - 1e-8))
    d = int(rng.geometric(p)) - 1
    return max(0, d), p


# Backward-compatible factory interfaces retained for scripts that import them.
class DelaySampler:
    def sample_delay(self, s_t: float, a: int, rng: np.random.Generator) -> int:
        raise NotImplementedError


class GeometricDelay(DelaySampler):
    def __init__(self, p: float):
        self.p = float(p)

    def sample_delay(self, s_t: float, a: int, rng: np.random.Generator) -> int:
        return int(rng.geometric(np.clip(self.p, 1e-6, 1.0 - 1e-8))) - 1


def make_delay_sampler(delay_cfg: dict, D_max: int, K: int):
    name = str(delay_cfg.get("name", "geometric"))
    if name == "geometric":
        return GeometricDelay(float(delay_cfg["p"]))
    raise ValueError("The revised EXP1 runner uses build_scenario_trace rather than make_delay_sampler.")


def delay_configs(K: int, T: int, D_max: int, seeds: list[int]):
    return {name: dict(cfg) for name, cfg in scenario_definitions().items()}

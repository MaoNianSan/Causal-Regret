from __future__ import annotations

"""Contextual learners for the revised EXP1 information structure.

All non-oracle learners observe X_t at decision time.  Arrival-time baselines
incorrectly attach a delayed outcome to the *arrival* context/action; source-aware
methods use the stored source-time (X_s, A_s).  Every method processes each
arrived source outcome once, avoiding batch-averaging sample-count advantages.
"""

from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np

from src.delay import CONTEXT_NOISE_SD, RHO, STATE_NOISE_SD, sigmoid
from src.utils import eps_schedule


CONTEXT_MIN = -3.8
CONTEXT_MAX = 3.8
N_CONTEXT_BINS = 21


def _loss(item: Any) -> float:
    return float(item["loss"]) if isinstance(item, dict) else float(item)


class ContextualTable:
    def __init__(self, K: int, n_bins: int = N_CONTEXT_BINS):
        self.K = int(K)
        self.n_bins = int(n_bins)
        self.reset()

    def reset(self) -> None:
        self.sum_loss = np.zeros((self.n_bins, self.K), dtype=float)
        self.count = np.zeros((self.n_bins, self.K), dtype=float)
        self.global_sum = np.zeros(self.K, dtype=float)
        self.global_count = np.zeros(self.K, dtype=float)

    def bin(self, x: float) -> int:
        scaled = (float(x) - CONTEXT_MIN) / (CONTEXT_MAX - CONTEXT_MIN)
        return int(np.clip(np.floor(scaled * self.n_bins), 0, self.n_bins - 1))

    def update(self, x: float, action: int, loss: float, weight: float = 1.0) -> None:
        w = float(weight)
        if w <= 0.0 or not np.isfinite(w):
            return
        b, a = self.bin(x), int(action)
        self.sum_loss[b, a] += w * float(loss)
        self.count[b, a] += w
        self.global_sum[a] += w * float(loss)
        self.global_count[a] += w

    def estimate(self, x: float) -> np.ndarray:
        b = self.bin(x)
        local = self.sum_loss[b] / np.maximum(self.count[b], 1e-12)
        global_mean = self.global_sum / np.maximum(self.global_count, 1e-12)
        # Context cells with no feedback fall back to action-global estimates;
        # actions with no global feedback are treated as unexplored.
        out = local.copy()
        no_local = self.count[b] <= 0.0
        out[no_local] = global_mean[no_local]
        out[self.global_count <= 0.0] = 0.0
        return out

    def count_at(self, x: float) -> np.ndarray:
        return self.count[self.bin(x)].copy()

    def choose(self, x: float, t: int, exploration: bool = True) -> int:
        counts = self.count_at(x)
        unseen = np.flatnonzero(counts <= 0.0)
        if len(unseen):
            return int(np.random.choice(unseen))
        if exploration and np.random.rand() < eps_schedule(t):
            return int(np.random.randint(self.K))
        values = self.estimate(x)
        best = np.flatnonzero(np.isclose(values, np.nanmin(values)))
        return int(np.random.choice(best))


class BaseAgent:
    def __init__(self, K: int):
        self.K = int(K)

    def reset(self) -> None:
        self.feedback_units = 0.0

    def observe_context(self, context: float, t: int, proxy_observation: float | None = None) -> None:
        del context, t, proxy_observation

    def act(self, env, t: int, context: float) -> int:
        raise NotImplementedError

    def observe(self, env, t: int, a_t: int, context_t: float, arrived: list[dict[str, Any]]) -> None:
        del env, t, a_t, context_t, arrived

    def pop_assignment_events(self) -> list[dict[str, Any]]:
        return []

    def proxy_state_estimate(self) -> float | None:
        return None


class OracleAgent(BaseAgent):
    def act(self, env, t: int, context: float) -> int:
        del t
        return int(env.optimal_action_from_context(context))


class ContextualArrivalAgent(BaseAgent):
    """Arrival-time learner: delayed outcomes are assigned to (X_t, A_t)."""

    def reset(self) -> None:
        super().reset()
        self.table = ContextualTable(self.K)

    def act(self, env, t: int, context: float) -> int:
        del env
        return self.table.choose(context, t, exploration=True)

    def observe(self, env, t: int, a_t: int, context_t: float, arrived: list[dict[str, Any]]) -> None:
        del env, t
        for item in arrived:
            self.table.update(context_t, int(a_t), _loss(item), 1.0)
            self.feedback_units += 1.0


class NaiveAgent(ContextualArrivalAgent):
    pass


class NaiveEWMAAgent(ContextualArrivalAgent):
    """Arrival-time EWMA with per-arrival updates, not batch means."""

    def __init__(self, K: int, ewma_mu: float = 0.98):
        super().__init__(K)
        self.ewma_mu = float(ewma_mu)

    def reset(self) -> None:
        super().reset()
        self.ema_sum = np.zeros((N_CONTEXT_BINS, self.K), dtype=float)
        self.ema_count = np.zeros((N_CONTEXT_BINS, self.K), dtype=float)

    def act(self, env, t: int, context: float) -> int:
        del env
        b = self.table.bin(context)
        counts = self.ema_count[b]
        unseen = np.flatnonzero(counts <= 0.0)
        if len(unseen):
            return int(np.random.choice(unseen))
        if np.random.rand() < eps_schedule(t):
            return int(np.random.randint(self.K))
        values = self.ema_sum[b] / np.maximum(counts, 1e-12)
        return int(np.random.choice(np.flatnonzero(np.isclose(values, values.min()))))

    def observe(self, env, t: int, a_t: int, context_t: float, arrived: list[dict[str, Any]]) -> None:
        del env, t
        b, a = self.table.bin(context_t), int(a_t)
        for item in arrived:
            y = _loss(item)
            self.table.update(context_t, a, y, 1.0)
            self.ema_sum[b] *= self.ewma_mu
            self.ema_count[b] *= self.ewma_mu
            self.ema_sum[b, a] += y
            self.ema_count[b, a] += 1.0
            self.feedback_units += 1.0


class DelayedUCBAgent(ContextualArrivalAgent):
    """Contextual delayed-UCB updated once per arrived source outcome."""

    def reset(self) -> None:
        super().reset()
        self.total_updates = 0

    def act(self, env, t: int, context: float) -> int:
        del env, t
        counts = self.table.count_at(context)
        unseen = np.flatnonzero(counts <= 0.0)
        if len(unseen):
            return int(np.random.choice(unseen))
        mean = self.table.estimate(context)
        bonus = np.sqrt(2.0 * np.log(max(2, self.total_updates + 1)) / np.maximum(counts, 1e-12))
        return int(np.argmin(mean - bonus))

    def observe(self, env, t: int, a_t: int, context_t: float, arrived: list[dict[str, Any]]) -> None:
        del env, t
        for item in arrived:
            self.table.update(context_t, int(a_t), _loss(item), 1.0)
            self.feedback_units += 1.0
            self.total_updates += 1


class DelayedEXP3Agent(BaseAgent):
    """Contextual EXP3-style arrival-time baseline with one update per arrival."""

    def __init__(self, K: int, gamma: float = 0.08):
        super().__init__(K)
        self.gamma = float(gamma)

    def reset(self) -> None:
        super().reset()
        self.table = ContextualTable(self.K)
        self.weights = np.ones((N_CONTEXT_BINS, self.K), dtype=float)
        self.last_probs = np.ones((N_CONTEXT_BINS, self.K), dtype=float) / self.K

    def act(self, env, t: int, context: float) -> int:
        del env, t
        b = self.table.bin(context)
        probs = (1.0 - self.gamma) * self.weights[b] / max(1e-12, self.weights[b].sum()) + self.gamma / self.K
        self.last_probs[b] = probs
        return int(np.random.choice(self.K, p=probs))

    def observe(self, env, t: int, a_t: int, context_t: float, arrived: list[dict[str, Any]]) -> None:
        del env, t
        b, a = self.table.bin(context_t), int(a_t)
        for item in arrived:
            y = _loss(item)
            self.table.update(context_t, a, y, 1.0)
            bounded = float(np.clip(y / 12.25, 0.0, 1.0))
            estimate = bounded / max(float(self.last_probs[b, a]), 1e-12)
            self.weights[b, a] *= float(np.exp(-self.gamma * estimate / self.K))
            self.feedback_units += 1.0


class SlidingWindowAgent(BaseAgent):
    def __init__(self, K: int, window: int = 250):
        super().__init__(K)
        self.window = int(window)

    def reset(self) -> None:
        super().reset()
        self.table = ContextualTable(self.K)
        self.records: deque[tuple[int, float, int, float]] = deque()

    def _rebuild(self, now: int) -> None:
        while self.records and self.records[0][0] < int(now) - self.window + 1:
            self.records.popleft()
        self.table.reset()
        for _, x, a, y in self.records:
            self.table.update(x, a, y)

    def act(self, env, t: int, context: float) -> int:
        del env
        self._rebuild(t)
        return self.table.choose(context, t, exploration=True)

    def observe(self, env, t: int, a_t: int, context_t: float, arrived: list[dict[str, Any]]) -> None:
        del env
        for item in arrived:
            self.records.append((int(t), float(context_t), int(a_t), _loss(item)))
            self.feedback_units += 1.0


class AnonymousDelayedAgent(ContextualArrivalAgent):
    """Each arrival contributes one total feedback unit, distributed uniformly."""

    def observe(self, env, t: int, a_t: int, context_t: float, arrived: list[dict[str, Any]]) -> None:
        del env, t, a_t
        for item in arrived:
            y = _loss(item)
            for a in range(self.K):
                self.table.update(context_t, a, y, weight=1.0 / self.K)
            self.feedback_units += 1.0


class CausalLabeledAgent(BaseAgent):
    """Exact source-time contextual attribution whenever source labels are visible."""

    def reset(self) -> None:
        super().reset()
        self.table = ContextualTable(self.K)

    def act(self, env, t: int, context: float) -> int:
        del env
        return self.table.choose(context, t, exploration=True)

    def observe(self, env, t: int, a_t: int, context_t: float, arrived: list[dict[str, Any]]) -> None:
        del env, t, a_t, context_t
        for item in arrived:
            if "src_a" in item and "src_x" in item:
                self.table.update(float(item["src_x"]), int(item["src_a"]), _loss(item), 1.0)
                self.feedback_units += 1.0


@dataclass
class AssignmentEvent:
    arrival_index: int
    labelled: bool
    candidate_source_times: np.ndarray
    posterior: np.ndarray
    entropy: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "arrival_index": int(self.arrival_index),
            "labelled": bool(self.labelled),
            "candidate_source_times": self.candidate_source_times.astype(int).tolist(),
            "posterior": self.posterior.astype(float).tolist(),
            "assignment_entropy": float(self.entropy),
        }


class CausalEMAgent(BaseAgent):
    r"""Soft attribution using only the learner's declared observable features.

    For an unlabelled arrival at clock ``u``, candidate sources are restricted
    to the finite delay window.  Outcome likelihoods are evaluated with the
    candidate source's saved decision feature.  Under state-structural delay,
    the default prior is *not* the plug-in ``p(X_s)`` approximation.  It is the
    Gaussian context-integrated likelihood

    .. math::
       P(D=d\mid Z_s) \approx \int p(s)(1-p(s))^d p(s\mid Z_s)\,ds,

    evaluated by Gauss--Hermite quadrature on the learner's binned observable
    feature.  ``misspecified_delay_model=True`` is a deliberately stationary
    geometric ablation, not a claim about an information-theoretic boundary.
    """

    _GH_NODES, _GH_WEIGHTS = np.polynomial.hermite.hermgauss(15)

    def __init__(
        self,
        K: int,
        delay_cfg: dict[str, Any],
        T: int,
        D_max: int,
        misspecified_delay_model: bool = False,
        L: int | None = None,
        sigma: float = 1.0,
        state_process: str = "ar1",
        context_noise_sd: float = CONTEXT_NOISE_SD,
        fixed_state: float | None = None,
    ):
        super().__init__(K)
        self.delay_cfg = dict(delay_cfg)
        self.T = int(T)
        self.D_max = int(D_max)
        self.L = int(L if L is not None else D_max + 1)
        self.sigma = float(sigma)
        self.misspecified_delay_model = bool(misspecified_delay_model)
        self.state_process = str(state_process)
        self.context_noise_sd = float(context_noise_sd)
        self.fixed_state = None if fixed_state is None else float(fixed_state)

    def reset(self) -> None:
        super().reset()
        self.table = ContextualTable(self.K)
        self.history: list[dict[str, float | int]] = []
        self._assignment_events: list[AssignmentEvent] = []
        self.assignment_entropy_sum = 0.0
        self.assignment_entropy_n = 0
        self.labelled_feature_alignment_errors: list[float] = []
        self._delay_weight_cache: dict[tuple[int, int, int, int, int], float] = {}

    def act(self, env, t: int, context: float) -> int:
        del env
        return self.table.choose(self._decision_feature(context), t, exploration=True)

    def _decision_feature(self, context: float) -> float:
        return float(context)

    @property
    def delay_likelihood_name(self) -> str:
        if self.misspecified_delay_model:
            return "stationary_geometric_ablation"
        if str(self.delay_cfg.get("name", "")) in {"state_structural", "action_structural"}:
            return "gaussian_observable_state_integrated_quadrature"
        return "known_exogenous_delay_law"

    def _feature_bin_center(self, feature: float) -> float:
        b = self.table.bin(float(feature))
        width = (CONTEXT_MAX - CONTEXT_MIN) / self.table.n_bins
        return float(CONTEXT_MIN + (float(b) + 0.5) * width)

    def _observable_state_moments(self, decision_feature: float) -> tuple[float, float]:
        """Return the Gaussian state posterior used by the declared learner.

        For a regular contextual EM learner, ``decision_feature=X_t`` and this
        is the analytic posterior under the untruncated stationary AR(1) prior.
        ProxyAgent overrides the history record with its Kalman posterior mean
        and variance, so it remains in its own training/decision feature space.
        """
        if self.state_process == "static":
            return float(self.fixed_state or 0.0), 0.0
        state_var = (STATE_NOISE_SD**2) / max(1e-12, 1.0 - RHO**2)
        noise_var = max(self.context_noise_sd**2, 1e-12)
        gain = state_var / (state_var + noise_var)
        return float(gain * float(decision_feature)), float(state_var * (1.0 - gain))

    def _history_record(self, t: int, action: int, context: float) -> dict[str, float | int]:
        feature = float(self._decision_feature(context))
        state_mean, state_var = self._observable_state_moments(feature)
        return {
            "t": int(t),
            "a": int(action),
            "x": feature,
            "delay_state_mean": float(state_mean),
            "delay_state_var": float(state_var),
        }

    def _labelled_source_feature(self, item: dict[str, Any]) -> float:
        """Feature used for a labelled source update.

        The default agent's source feature is the saved source-time context.
        ProxyAgent overrides this to use its *saved source-time proxy feature*,
        never an environment-only source context.
        """
        src_t = int(item["src_t"])
        fallback = float(self.history[max(0, src_t)]["x"])
        return float(item.get("src_x", fallback))

    def _binned_delay_state_moments(self, feature: float, state_mean: float, state_var: float) -> tuple[float, float]:
        """Posterior moments conditional on the learner's binned feature."""
        del state_mean, state_var
        return self._observable_state_moments(self._feature_bin_center(float(feature)))

    def _integrated_structural_weight(self, lag: int, feature: float, state_mean: float, state_var: float, alpha: float = 0.0) -> float:
        """Approximate ``P(D=lag | observable feature)`` with cached quadrature.

        The observable feature is deliberately binned because the learning table
        is binned as well.  This prevents an unbounded per-arrival integration
        cost while retaining the correct conditioning object ``P(D|Z_s)`` rather
        than the old plug-in ``P(D|X_s=s)`` shortcut.
        """
        mean, var = self._binned_delay_state_moments(float(feature), float(state_mean), float(state_var))
        mean_key = int(np.round(float(mean) * 1000.0))
        var_key = int(np.round(max(float(var), 0.0) * 10000.0))
        alpha_key = int(np.round(float(alpha) * 1000.0))
        key = (int(lag), mean_key, var_key, alpha_key, int(self.misspecified_delay_model))
        cached = self._delay_weight_cache.get(key)
        if cached is not None:
            return float(cached)
        if var <= 1e-12:
            states = np.asarray([mean], dtype=float)
            weights = np.asarray([1.0], dtype=float)
        else:
            states = mean + np.sqrt(2.0 * float(var)) * self._GH_NODES
            weights = self._GH_WEIGHTS / np.sqrt(np.pi)
        beta = float(self.delay_cfg.get("beta", 1.0))
        p = np.clip(np.asarray(sigmoid(beta * states + float(alpha)), dtype=float), 1e-8, 1.0 - 1e-8)
        value = float(np.sum(weights * p * np.power(1.0 - p, int(lag))))
        value = max(value, 1e-300)
        self._delay_weight_cache[key] = value
        return value

    def _delay_prior(
        self,
        lags: np.ndarray,
        features: np.ndarray,
        state_means: np.ndarray,
        state_vars: np.ndarray,
        actions: np.ndarray,
    ) -> np.ndarray:
        name = str(self.delay_cfg.get("name", "geometric"))
        lags = np.asarray(lags, dtype=int)
        if self.misspecified_delay_model:
            # Explicit stationary-lag ablation.  It deliberately discards source
            # state/context dependence and must not be interpreted as a theorem.
            p = 1.0 / 16.0
            weights = p * np.power(1.0 - p, lags)
        elif name == "geometric":
            p = float(self.delay_cfg["p"])
            weights = p * np.power(1.0 - p, lags)
        elif name == "mixture":
            w = float(self.delay_cfg["w"])
            pf = float(self.delay_cfg["p_fast"])
            ps = float(self.delay_cfg["p_slow"])
            weights = w * pf * np.power(1.0 - pf, lags) + (1.0 - w) * ps * np.power(1.0 - ps, lags)
        elif name in {"state_structural", "action_structural"}:
            alpha = np.zeros_like(lags, dtype=float)
            if name == "action_structural":
                alpha_values = np.asarray(self.delay_cfg.get("alpha", np.zeros(self.K)), dtype=float)
                alpha = alpha_values[np.asarray(actions, dtype=int)]
            weights = np.asarray(
                [
                    self._integrated_structural_weight(int(d), float(f), float(m), float(v), float(a))
                    for d, f, m, v, a in zip(lags, features, state_means, state_vars, alpha)
                ],
                dtype=float,
            )
        elif name in {"zero", "fixed"}:
            target = 0 if name == "zero" else int(self.delay_cfg.get("delay_value", 0))
            weights = np.where(lags.astype(int) == target, 1.0, 1e-12)
        else:
            weights = np.ones_like(lags, dtype=float)
        weights = np.clip(weights, 1e-300, None)
        return weights / np.sum(weights)

    def _candidate_records(
        self, now_t: int
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        start = max(0, len(self.history) - self.L)
        records = self.history[start:][::-1]  # newest -> oldest, lag 0..L
        source_times = np.asarray([int(r["t"]) for r in records], dtype=int)
        actions = np.asarray([int(r["a"]) for r in records], dtype=int)
        features = np.asarray([float(r["x"]) for r in records], dtype=float)
        state_means = np.asarray([float(r["delay_state_mean"]) for r in records], dtype=float)
        state_vars = np.asarray([float(r["delay_state_var"]) for r in records], dtype=float)
        lags = int(now_t) - source_times
        return source_times, actions, features, state_means, state_vars, lags

    @staticmethod
    def _entropy(r: np.ndarray) -> float:
        q = np.clip(np.asarray(r, dtype=float), 1e-12, 1.0)
        q = q / q.sum()
        return float(-np.sum(q * np.log(q)))

    def _posterior(self, y: float, now_t: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        source_times, actions, features, state_means, state_vars, lags = self._candidate_records(now_t)
        if len(source_times) == 0:
            return source_times, actions, features, np.zeros(0, dtype=float)
        prior = self._delay_prior(lags, features, state_means, state_vars, actions)
        means = np.asarray([self.table.estimate(x)[a] for x, a in zip(features, actions)], dtype=float)
        sigma2 = max(self.sigma**2, 1e-8)
        score = -0.5 * ((float(y) - means) ** 2) / sigma2
        score -= float(np.max(score))
        posterior = prior * np.exp(score)
        if float(np.sum(posterior)) <= 0.0:
            posterior = prior
        posterior = posterior / np.sum(posterior)
        return source_times, actions, features, posterior

    def observe(self, env, t: int, a_t: int, context_t: float, arrived: list[dict[str, Any]]) -> None:
        del env
        self.history.append(self._history_record(int(t), int(a_t), float(context_t)))
        self._assignment_events = []
        for idx, item in enumerate(arrived):
            y = _loss(item)
            if "src_a" in item and "src_t" in item:
                src_t = int(item["src_t"])
                source_feature = float(self._labelled_source_feature(item))
                if 0 <= src_t < len(self.history):
                    expected_feature = float(self.history[src_t]["x"])
                    self.labelled_feature_alignment_errors.append(abs(source_feature - expected_feature))
                self.table.update(source_feature, int(item["src_a"]), y, 1.0)
                self.feedback_units += 1.0
                self._assignment_events.append(
                    AssignmentEvent(idx, True, np.asarray([src_t]), np.asarray([1.0]), 0.0)
                )
                continue
            src_times, actions, features, posterior = self._posterior(y, int(t))
            if len(posterior) == 0:
                continue
            for source_feature, source_a, weight in zip(features, actions, posterior):
                self.table.update(float(source_feature), int(source_a), y, float(weight))
            self.feedback_units += 1.0
            entropy = self._entropy(posterior)
            self.assignment_entropy_sum += entropy
            self.assignment_entropy_n += 1
            self._assignment_events.append(AssignmentEvent(idx, False, src_times, posterior, entropy))

    def pop_assignment_events(self) -> list[dict[str, Any]]:
        out = [event.as_dict() for event in self._assignment_events]
        self._assignment_events = []
        return out

    def labelled_feature_alignment_max(self) -> float:
        return float(max(self.labelled_feature_alignment_errors)) if self.labelled_feature_alignment_errors else 0.0


class KalmanStateProxy:
    def __init__(self, observation_noise_sd: float):
        self.observation_noise_sd = max(float(observation_noise_sd), 1e-6)
        self.reset()

    def reset(self) -> None:
        self.mean = 0.0
        self.var = (STATE_NOISE_SD**2) / max(1e-9, 1.0 - RHO**2)

    def update(self, observation: float) -> float:
        pred_mean = RHO * self.mean
        pred_var = RHO**2 * self.var + STATE_NOISE_SD**2
        obs_var = self.observation_noise_sd**2
        gain = pred_var / (pred_var + obs_var)
        self.mean = pred_mean + gain * (float(observation) - pred_mean)
        self.var = (1.0 - gain) * pred_var
        return float(self.mean)


class ProxyAgent(CausalEMAgent):
    r"""State-proxy attribution learner with an explicit filtered \hat S_t.

    The proxy is generated from decision-time observations only.  Its quality is
    measured at every t by |\hat S_t-S_t| in the runner, rather than by a
    terminal inverse reconstruction.
    """

    def __init__(
        self,
        K: int,
        T: int,
        delay: dict[str, Any],
        D_max: int,
        observation_noise_sd: float,
        L: int | None = None,
        sigma: float = 1.0,
        **_: Any,
    ):
        super().__init__(K=K, delay_cfg=delay, T=T, D_max=D_max, L=L, sigma=sigma)
        self.observation_noise_sd = float(observation_noise_sd)

    def reset(self) -> None:
        super().reset()
        self.filter = KalmanStateProxy(self.observation_noise_sd)
        self.current_proxy_state = 0.0

    def observe_context(self, context: float, t: int, proxy_observation: float | None = None) -> None:
        del context, t
        value = float(proxy_observation if proxy_observation is not None else context)
        self.current_proxy_state = self.filter.update(value)

    def _decision_feature(self, context: float) -> float:
        del context
        return float(self.current_proxy_state)

    def _history_record(self, t: int, action: int, context: float) -> dict[str, float | int]:
        del context
        # The Kalman mean/variance are exactly the proxy learner's decision-time
        # state representation.  Saving them makes labelled and unlabelled
        # updates use the same feature geometry as action selection.
        return {
            "t": int(t),
            "a": int(action),
            "x": float(self.current_proxy_state),
            "delay_state_mean": float(self.current_proxy_state),
            "delay_state_var": float(self.filter.var),
        }

    def _binned_delay_state_moments(self, feature: float, state_mean: float, state_var: float) -> tuple[float, float]:
        # Here the decision feature is itself a Kalman posterior mean.  Binning
        # that mean (while retaining its saved posterior variance) keeps the
        # delay prior and outcome table in the same proxy feature geometry.
        del state_mean
        return float(self._feature_bin_center(float(feature))), float(state_var)

    def _labelled_source_feature(self, item: dict[str, Any]) -> float:
        src_t = int(item["src_t"])
        if src_t < 0 or src_t >= len(self.history):
            raise IndexError(f"labelled source time {src_t} is unavailable in proxy history")
        # Never use item['src_x'] here.  It belongs to the ordinary contextual
        # feature space and would reintroduce the train/decision mismatch.
        return float(self.history[src_t]["x"])

    def proxy_state_estimate(self) -> float | None:
        return float(self.current_proxy_state)

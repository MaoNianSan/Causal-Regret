"""Online policies for Exp4.  Every feedback update occurs after arrival."""

from __future__ import annotations

import numpy as np


class ContextualUCB:
    """Vectorised contextual UCB statistics for low-overhead soft attribution."""

    def __init__(
        self, n_actions: int, n_contexts: int, exploration: float = 1.25
    ) -> None:
        self.n_actions = int(n_actions)
        self.n_contexts = int(n_contexts)
        self.exploration = float(exploration)
        self.count = np.zeros((self.n_contexts, self.n_actions), dtype=float)
        self.loss_sum = np.zeros((self.n_contexts, self.n_actions), dtype=float)

    def choose(self, t: int, context: int) -> int:
        context = int(context)
        count = self.count[context]
        unseen = np.flatnonzero(count <= 0.0)
        if len(unseen):
            return int(unseen[t % len(unseen)])
        mean = self.loss_sum[context] / count
        radius = self.exploration * np.sqrt(np.log(max(2, t + 1)) / count)
        return int(np.argmin(mean - radius))

    def update(
        self, context: int, action: int, loss: float, weight: float = 1.0
    ) -> None:
        if weight <= 0.0:
            return
        self.count[int(context), int(action)] += float(weight)
        self.loss_sum[int(context), int(action)] += float(weight) * float(loss)

    def batch_update(
        self,
        contexts: np.ndarray,
        actions: np.ndarray,
        losses: np.ndarray,
        weights: np.ndarray,
    ) -> None:
        if not len(contexts):
            return
        contexts = np.asarray(contexts, dtype=int)
        actions = np.asarray(actions, dtype=int)
        losses = np.asarray(losses, dtype=float)
        weights = np.asarray(weights, dtype=float)
        np.add.at(self.count, (contexts, actions), weights)
        np.add.at(self.loss_sum, (contexts, actions), weights * losses)


class ArrivalTimeNaiveUCB:
    """Anonymous arrivals are deliberately assigned to the current action/context."""

    def __init__(self, n_actions: int, n_contexts: int) -> None:
        self.stats = ContextualUCB(n_actions, n_contexts)

    def choose(self, t: int, context: int) -> int:
        return self.stats.choose(t, context)

    def observe(
        self, current_action: int, current_context: int, anonymous_losses: list[float]
    ) -> None:
        for loss in anonymous_losses:
            self.stats.update(current_context, current_action, loss)


class SourceLabelledReferenceUCB:
    """Reference route: every arriving loss carries its source identifier."""

    def __init__(self, n_actions: int, n_contexts: int) -> None:
        self.stats = ContextualUCB(n_actions, n_contexts)

    def choose(self, t: int, context: int) -> int:
        return self.stats.choose(t, context)

    def observe(
        self,
        labelled_events: list[tuple[int, float]],
        action_history: np.ndarray,
        context_history: np.ndarray,
    ) -> None:
        for source, loss in labelled_events:
            self.stats.update(
                int(context_history[source]), int(action_history[source]), loss
            )


class ProxyLabelRecoveryUCB:
    """Partial-label UCB with exact and fixed-rule proxy soft attribution.

    Exact retained labels update the source action/context.  For each anonymous
    arrival at time ``u``, the policy distributes its loss over feasible historical
    sources ``s in [u-d_max, u)`` using stored observable proxy history, an RBF
    similarity kernel, and a fixed recency prior.  It never receives the hidden
    source index of that arrival.  This is a transparent proxy-recovery route, not
    an optimality benchmark for every possible proxy-only algorithm.
    """

    def __init__(
        self,
        n_actions: int,
        n_contexts: int,
        proxy_history: np.ndarray,
        max_delay: int,
        bandwidth: float = 0.55,
        recency_decay: float = 0.035,
    ) -> None:
        self.stats = ContextualUCB(n_actions, n_contexts)
        self.proxy_history = proxy_history
        self.max_delay = int(max_delay)
        self.bandwidth = float(bandwidth)
        self.recency_decay = float(recency_decay)
        self.exact_updates = 0
        self.soft_updates = 0

    def choose(self, t: int, context: int) -> int:
        return self.stats.choose(t, context)

    def _candidate_weights(self, arrival_t: int) -> tuple[np.ndarray, np.ndarray]:
        lower = max(0, int(arrival_t) - self.max_delay)
        candidates = np.arange(lower, int(arrival_t), dtype=int)
        if len(candidates) == 0:
            return candidates, np.empty(0, dtype=float)
        proxy_gap = self.proxy_history[candidates] - self.proxy_history[int(arrival_t)]
        squared_distance = np.einsum("ij,ij->i", proxy_gap, proxy_gap)
        recency = int(arrival_t) - candidates
        log_weight = (
            -squared_distance / (2.0 * self.bandwidth**2) - self.recency_decay * recency
        )
        log_weight -= float(np.max(log_weight))
        weights = np.exp(log_weight)
        weights /= float(weights.sum())
        return candidates, weights

    def observe(
        self,
        arrival_t: int,
        labelled_events: list[tuple[int, float]],
        anonymous_losses: list[float],
        action_history: np.ndarray,
        context_history: np.ndarray,
    ) -> None:
        for source, loss in labelled_events:
            self.stats.update(
                int(context_history[source]), int(action_history[source]), loss
            )
            self.exact_updates += 1
        if not anonymous_losses:
            return
        candidates, weights = self._candidate_weights(arrival_t)
        if len(candidates) == 0:
            return
        # All anonymous arrivals at the same time share the same feasible source
        # set and weights.  Their sufficient statistics can therefore be updated
        # in one vectorised batch without changing the sequential estimator.
        mean_loss = float(np.mean(anonymous_losses))
        multiplicity = float(len(anonymous_losses))
        self.stats.batch_update(
            context_history[candidates],
            action_history[candidates],
            np.full(len(candidates), mean_loss, dtype=float),
            multiplicity * weights,
        )
        self.soft_updates += int(len(anonymous_losses))


class ObservableHistorySurrogate:
    """Anonymous arrival-history surrogate with exponential forgetting.

    The route uses the common observable decision-time context, but neither a source
    label nor a direct proxy-to-action map.  Anonymous losses are attributed to the
    current arrival-time context/action with exponential forgetting, making it a
    nonstationary anonymous-history comparator rather than an oracle proxy policy.
    """

    def __init__(
        self,
        n_actions: int,
        n_contexts: int,
        alpha: float = 0.08,
        exploration: float = 1.40,
    ) -> None:
        self.n_actions = int(n_actions)
        self.n_contexts = int(n_contexts)
        self.alpha = float(alpha)
        self.exploration = float(exploration)
        self.ema_loss = np.full((self.n_contexts, self.n_actions), 0.50, dtype=float)
        self.effective_count = np.zeros((self.n_contexts, self.n_actions), dtype=float)

    def choose(self, t: int, context: int) -> int:
        context = int(context)
        unseen = np.flatnonzero(self.effective_count[context] < 0.25)
        if len(unseen):
            return int(unseen[t % len(unseen)])
        bonus = self.exploration * np.sqrt(
            np.log(max(2, t + 1)) / np.maximum(self.effective_count[context], 1e-8)
        )
        return int(np.argmin(self.ema_loss[context] - bonus))

    def observe(
        self, current_action: int, current_context: int, anonymous_losses: list[float]
    ) -> None:
        if not anonymous_losses:
            return
        context = int(current_context)
        action = int(current_action)
        for loss in anonymous_losses:
            self.ema_loss[context, action] = (1.0 - self.alpha) * self.ema_loss[
                context, action
            ] + self.alpha * float(loss)
            self.effective_count[context, action] = (
                1.0 - self.alpha
            ) * self.effective_count[context, action] + self.alpha


class NoisyOracleProxyDiagnostic:
    """Diagnostic direct mapping from a noisy simulator-emitted proxy to actions."""

    def __init__(self, centers: np.ndarray, proxy_history: np.ndarray) -> None:
        self.centers = centers
        self.proxy_history = proxy_history

    def choose(self, t: int, context: int | None = None) -> int:
        distances = ((self.centers - self.proxy_history[int(t)]) ** 2).sum(axis=1)
        return int(np.argmin(distances))

    def observe(self, **_: object) -> None:
        return


class ProxyOracleDiagnostic:
    """Latent-state diagnostic; never a deployable policy."""

    def __init__(self, centers: np.ndarray, latent_states: np.ndarray) -> None:
        self.centers = centers
        self.latent_states = latent_states

    def choose(self, t: int, context: int | None = None) -> int:
        distances = ((self.centers - self.latent_states[int(t)]) ** 2).sum(axis=1)
        return int(np.argmin(distances))

    def observe(self, **_: object) -> None:
        return

"""Appendix-only scalar-feedback learners for Exp4.

These learners never receive the simulator-only structural loss map.  They choose
an action before processing observations arriving at the same clock.
"""

from __future__ import annotations

import numpy as np

import config


class ContextualUCBStatistics:
    def __init__(
        self,
        num_actions: int,
        num_contexts: int,
        exploration_coefficient: float = 1.25,
    ) -> None:
        self.num_actions = int(num_actions)
        self.num_contexts = int(num_contexts)
        self.exploration_coefficient = float(exploration_coefficient)
        self.effective_count = np.zeros(
            (self.num_contexts, self.num_actions), dtype=np.float64
        )
        self.loss_sum = np.zeros_like(self.effective_count)

    def choose_action(self, decision_round: int, context_id: int) -> int:
        context_id = int(context_id)
        counts = self.effective_count[context_id]
        unseen_actions = np.flatnonzero(counts <= 0.0)
        if len(unseen_actions):
            return int(unseen_actions[decision_round % len(unseen_actions)])
        mean_loss = self.loss_sum[context_id] / counts
        confidence_radius = self.exploration_coefficient * np.sqrt(
            np.log(max(2, decision_round + 1)) / counts
        )
        return int(np.argmin(mean_loss - confidence_radius))

    def update(
        self,
        context_id: int,
        action_id: int,
        factual_loss: float,
        weight: float = 1.0,
    ) -> None:
        if weight <= 0.0:
            return
        self.effective_count[int(context_id), int(action_id)] += float(weight)
        self.loss_sum[int(context_id), int(action_id)] += float(weight) * float(
            factual_loss
        )

    def batch_update(
        self,
        context_ids: np.ndarray,
        action_ids: np.ndarray,
        factual_losses: np.ndarray,
        weights: np.ndarray,
    ) -> None:
        if len(context_ids) == 0:
            return
        np.add.at(self.effective_count, (context_ids, action_ids), weights)
        np.add.at(self.loss_sum, (context_ids, action_ids), weights * factual_losses)


class ArrivalTimeUCB:
    def __init__(self, num_actions: int, num_contexts: int) -> None:
        self.statistics = ContextualUCBStatistics(num_actions, num_contexts)

    def choose_action(self, decision_round: int, context_id: int) -> int:
        return self.statistics.choose_action(decision_round, context_id)

    def observe(
        self,
        current_action: int,
        current_context: int,
        anonymous_losses: list[float],
    ) -> None:
        for factual_loss in anonymous_losses:
            self.statistics.update(current_context, current_action, factual_loss)


class SourceBoundUCB:
    def __init__(self, num_actions: int, num_contexts: int) -> None:
        self.statistics = ContextualUCBStatistics(num_actions, num_contexts)

    def choose_action(self, decision_round: int, context_id: int) -> int:
        return self.statistics.choose_action(decision_round, context_id)

    def observe(
        self,
        labelled_events: list[tuple[int, float]],
        action_history: np.ndarray,
        context_history: np.ndarray,
    ) -> None:
        for source_round, factual_loss in labelled_events:
            self.statistics.update(
                int(context_history[source_round]),
                int(action_history[source_round]),
                factual_loss,
            )


class ProxyLabelUCB:
    def __init__(
        self,
        num_actions: int,
        num_contexts: int,
        attribution_proxy: np.ndarray,
    ) -> None:
        self.statistics = ContextualUCBStatistics(num_actions, num_contexts)
        self.attribution_proxy = attribution_proxy

    def choose_action(self, decision_round: int, context_id: int) -> int:
        return self.statistics.choose_action(decision_round, context_id)

    def _candidate_weights(self, arrival_clock: int, decision_horizon: int) -> tuple[np.ndarray, np.ndarray]:
        lower = max(0, int(arrival_clock) - config.PARAMETERS.maximum_candidate_delay)
        upper = min(int(arrival_clock), int(decision_horizon))
        candidates = np.arange(lower, upper, dtype=np.int64)
        if len(candidates) == 0:
            raise RuntimeError("Proxy-label learner found no historical source candidates.")
        proxy_difference = (
            self.attribution_proxy[candidates]
            - self.attribution_proxy[int(arrival_clock)]
        )
        squared_distance = np.einsum(
            "ij,ij->i", proxy_difference, proxy_difference, optimize=True
        )
        recency = int(arrival_clock) - candidates
        log_weight = (
            -squared_distance / (2.0 * config.PARAMETERS.proxy_kernel_bandwidth**2)
            - config.PARAMETERS.recency_decay_rate * recency
        )
        log_weight -= float(np.max(log_weight))
        weights = np.exp(log_weight)
        weights /= float(weights.sum())
        return candidates, weights

    def observe(
        self,
        arrival_clock: int,
        labelled_events: list[tuple[int, float]],
        anonymous_losses: list[float],
        action_history: np.ndarray,
        context_history: np.ndarray,
        decision_horizon: int,
    ) -> None:
        for source_round, factual_loss in labelled_events:
            self.statistics.update(
                int(context_history[source_round]),
                int(action_history[source_round]),
                factual_loss,
            )
        if not anonymous_losses:
            return
        candidates, weights = self._candidate_weights(
            arrival_clock, decision_horizon
        )
        mean_loss = float(np.mean(anonymous_losses))
        multiplicity = float(len(anonymous_losses))
        self.statistics.batch_update(
            context_history[candidates],
            action_history[candidates],
            np.full(len(candidates), mean_loss, dtype=np.float64),
            multiplicity * weights,
        )


class HistorySurrogateUCB:
    def __init__(
        self,
        num_actions: int,
        num_contexts: int,
        exploration_coefficient: float = 1.40,
    ) -> None:
        self.num_actions = int(num_actions)
        self.num_contexts = int(num_contexts)
        self.exploration_coefficient = float(exploration_coefficient)
        self.ema_loss = np.full(
            (self.num_contexts, self.num_actions), 0.5, dtype=np.float64
        )
        self.effective_count = np.zeros_like(self.ema_loss)

    def choose_action(self, decision_round: int, context_id: int) -> int:
        context_id = int(context_id)
        unseen_actions = np.flatnonzero(self.effective_count[context_id] < 0.25)
        if len(unseen_actions):
            return int(unseen_actions[decision_round % len(unseen_actions)])
        confidence_radius = self.exploration_coefficient * np.sqrt(
            np.log(max(2, decision_round + 1))
            / np.maximum(self.effective_count[context_id], 1e-8)
        )
        return int(np.argmin(self.ema_loss[context_id] - confidence_radius))

    def observe(
        self,
        current_action: int,
        current_context: int,
        anonymous_losses: list[float],
    ) -> None:
        if not anonymous_losses:
            return
        context_id = int(current_context)
        action_id = int(current_action)
        for factual_loss in anonymous_losses:
            self.ema_loss[context_id, action_id] = (
                (1.0 - config.PARAMETERS.history_ema_rate)
                * self.ema_loss[context_id, action_id]
                + config.PARAMETERS.history_ema_rate * float(factual_loss)
            )
            self.effective_count[context_id, action_id] = (
                (1.0 - config.PARAMETERS.history_ema_rate)
                * self.effective_count[context_id, action_id]
                + config.PARAMETERS.history_ema_rate
            )

from __future__ import annotations

"""Contextual Delayed EXP3 with explicit scalar-feedback binding."""

from dataclasses import dataclass
import hashlib

import numpy as np

from src.contracts import ContractError, ScientificInvariantError


@dataclass(frozen=True)
class SourceFeedbackEvent:
    event_id: str
    source_round: int
    arrival_clock: int
    source_context_cell: int
    source_action: int
    source_action_probability: float
    factual_loss: float


class ContextualDelayedEXP3:
    """One EXP3 instance per frozen context cell.

    The class deliberately exposes no structural loss matrix, route map, best
    action, or future queue.  It accepts only context-cell indices and factual
    scalar losses.
    """

    def __init__(
        self,
        k_actions: int,
        context_boundaries: np.ndarray,
        gamma: float,
        eta: float,
    ) -> None:
        self.k_actions = int(k_actions)
        self.context_boundaries = np.asarray(context_boundaries, dtype=float)
        if self.context_boundaries.ndim != 1:
            raise ContractError("context_boundaries must be one-dimensional")
        if np.any(np.diff(self.context_boundaries) <= 0):
            raise ContractError("context boundaries must be strictly increasing")
        self.n_context_cells = self.context_boundaries.size + 1
        self.gamma = float(gamma)
        self.eta = float(eta)
        if not 0.0 < self.gamma <= 1.0:
            raise ContractError("EXP3 gamma must lie in (0,1]")
        if not self.eta > 0.0:
            raise ContractError("EXP3 eta must be positive")
        self.log_weights = np.zeros((self.n_context_cells, self.k_actions), dtype=float)
        self.n_updates = 0

    def context_cell(self, context: float) -> int:
        if not np.isfinite(context):
            raise ScientificInvariantError("context must be finite")
        return int(np.searchsorted(self.context_boundaries, float(context), side="right"))

    def action_probabilities(self, context_cell: int) -> np.ndarray:
        cell = int(context_cell)
        if not 0 <= cell < self.n_context_cells:
            raise ContractError(f"context_cell={cell} outside valid range")
        logits = self.log_weights[cell]
        shifted = logits - np.max(logits)
        normalized = np.exp(shifted)
        normalized /= np.sum(normalized)
        probabilities = (1.0 - self.gamma) * normalized + self.gamma / self.k_actions
        if not np.all(np.isfinite(probabilities)) or not np.isclose(np.sum(probabilities), 1.0):
            raise ScientificInvariantError("invalid EXP3 action probabilities")
        return probabilities

    def choose_action(self, context_cell: int, uniform_draw: float) -> tuple[int, float]:
        u = float(uniform_draw)
        if not 0.0 <= u < 1.0:
            raise ContractError("uniform_draw must lie in [0,1)")
        probabilities = self.action_probabilities(context_cell)
        action = int(np.searchsorted(np.cumsum(probabilities), u, side="right"))
        action = min(action, self.k_actions - 1)
        return action, float(probabilities[action])

    def apply_update(
        self,
        context_cell: int,
        action: int,
        selected_probability: float,
        factual_loss: float,
    ) -> None:
        cell = int(context_cell)
        arm = int(action)
        probability = float(selected_probability)
        loss = float(factual_loss)
        if not 0 <= cell < self.n_context_cells:
            raise ContractError("invalid context cell in EXP3 update")
        if not 0 <= arm < self.k_actions:
            raise ContractError("invalid action in EXP3 update")
        if not 0.0 < probability <= 1.0 or not np.isfinite(probability):
            raise ScientificInvariantError("selected probability must be finite and positive")
        if not -1e-12 <= loss <= 1.0 + 1e-12 or not np.isfinite(loss):
            raise ScientificInvariantError(
                f"factual loss {loss} outside the frozen [0,1] structural scale"
            )
        estimated_loss = loss / probability
        if not np.isfinite(estimated_loss):
            raise ScientificInvariantError("non-finite importance-weighted loss")
        self.log_weights[cell, arm] -= self.eta * estimated_loss
        # Translation is probability-invariant and prevents long-run overflow.
        self.log_weights[cell] -= np.max(self.log_weights[cell])
        self.n_updates += 1

    def state_hash(self) -> str:
        h = hashlib.sha256()
        h.update(np.ascontiguousarray(self.log_weights).tobytes())
        h.update(str(self.n_updates).encode("ascii"))
        return h.hexdigest()

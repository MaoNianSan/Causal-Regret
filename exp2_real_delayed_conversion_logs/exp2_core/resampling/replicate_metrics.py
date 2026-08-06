from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

from contracts import PRIMARY_SOURCE_ROUTE_ORDER, ScientificInvariantError

from .draws import _BootstrapState


def _top_k_indices(scores: np.ndarray, tie_rank: np.ndarray, top_k: int) -> np.ndarray:
    order = np.lexsort((tie_rank, -np.asarray(scores, dtype=float)))
    return order[:top_k]


def _route_vectors(
    state: _BootstrapState, multiplicity: np.ndarray
) -> dict[str, dict[str, np.ndarray]]:
    outputs: dict[str, dict[str, np.ndarray]] = {}
    for route_id, matrix in state.route_matrices.items():
        credits = np.asarray(matrix.T.dot(multiplicity), dtype=float).reshape(-1)
        total = float(credits.sum())
        if total <= 0:
            raise ScientificInvariantError(f"Bootstrap route {route_id} has nonpositive credit.")
        allocation = credits / total
        scores = credits / state.eligible_impressions
        outputs[route_id] = {"credits": credits, "allocation": allocation, "scores": scores}
    return outputs


def _pair_metrics(
    vectors: dict[str, dict[str, np.ndarray]],
    left_route: str,
    right_route: str,
    state: _BootstrapState,
) -> dict[str, float | int]:
    left = vectors[left_route]
    right = vectors[right_route]
    tv = 0.5 * float(np.abs(left["allocation"] - right["allocation"]).sum())
    left_top = set(_top_k_indices(left["scores"], state.tie_rank, state.top_k).tolist())
    right_top = set(_top_k_indices(right["scores"], state.tie_rank, state.top_k).tolist())
    overlap = len(left_top.intersection(right_top)) / float(state.top_k)
    pair_key = (left_route, right_route)
    support = state.frozen_support_masks[pair_key]
    support_count = int(support.sum())
    full_sample_support_count = state.frozen_support_counts[pair_key]
    if support_count != full_sample_support_count:
        raise ScientificInvariantError("Bootstrap Kendall support changed within a replicate.")
    left_scores = left["scores"][support]
    right_scores = right["scores"][support]
    left_constant = bool(np.unique(left_scores).size <= 1)
    right_constant = bool(np.unique(right_scores).size <= 1)
    zero_mass_vector = bool(
        np.isclose(left["credits"][support].sum(), 0.0, atol=1e-15, rtol=0.0)
        or np.isclose(right["credits"][support].sum(), 0.0, atol=1e-15, rtol=0.0)
    )
    if support_count >= 2 and not (left_constant or right_constant):
        tau = float(
            kendalltau(
                left_scores,
                right_scores,
                variant="b",
                nan_policy="omit",
            ).statistic
        )
    else:
        tau = float("nan")
    return {
        "allocation_tv": float(np.clip(tv, 0.0, 1.0)),
        "top_k_overlap": overlap,
        "top_k_set_disagreement": 1.0 - overlap,
        "kendall_tau_b": tau,
        "common_active_cell_count": full_sample_support_count,
        "full_sample_support_count": full_sample_support_count,
        "bootstrap_support_count": support_count,
        "support_frozen": True,
        "constant_vector": left_constant or right_constant,
        "zero_mass_vector": zero_mass_vector,
    }


def run_replicate(
    replication_id: int, seed: int, state: _BootstrapState
) -> list[dict[str, object]]:
    rng = np.random.default_rng(seed)
    multiplicity = rng.multinomial(
        state.n_users, np.full(state.n_users, 1.0 / state.n_users, dtype=float)
    ).astype(float)
    vectors = _route_vectors(state, multiplicity)
    rows: list[dict[str, object]] = []
    for route_id in PRIMARY_SOURCE_ROUTE_ORDER:
        metrics = _pair_metrics(
            vectors, "arrival_time_accounting_anchor", route_id, state
        )
        rows.append(
            {
                "replication_id": replication_id,
                "record_type": "arrival_displacement",
                "route_id": route_id,
                "route_left": "arrival_time_accounting_anchor",
                "route_right": route_id,
                "top_k": state.top_k,
                **metrics,
            }
        )
    for left_route, right_route in combinations(PRIMARY_SOURCE_ROUTE_ORDER, 2):
        metrics = _pair_metrics(vectors, left_route, right_route, state)
        rows.append(
            {
                "replication_id": replication_id,
                "record_type": "source_route_pair",
                "route_id": pd.NA,
                "route_left": left_route,
                "route_right": right_route,
                "top_k": state.top_k,
                **metrics,
            }
        )
    return rows

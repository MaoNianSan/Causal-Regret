from __future__ import annotations

import os
from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

from contracts import PRIMARY_ROUTE_ORDER, PRIMARY_SOURCE_ROUTE_ORDER, ScientificInvariantError
from ..metrics import PairwiseMetricState


@dataclass(frozen=True)
class _BootstrapState:
    route_matrices: dict[str, csr_matrix]
    eligible_impressions: np.ndarray
    tie_rank: np.ndarray
    n_users: int
    top_k: int
    frozen_support_masks: dict[tuple[str, str], np.ndarray]
    frozen_support_counts: dict[tuple[str, str], int]


def resolve_n_jobs(value: str | int, *, reserve_cores: int = 2) -> int:
    if isinstance(value, int):
        if value <= 0:
            raise ValueError("n_jobs must be positive.")
        return value
    text = str(value).strip().lower()
    if text != "auto":
        parsed = int(text)
        if parsed <= 0:
            raise ValueError("n_jobs must be positive.")
        return parsed
    available = os.cpu_count() or 1
    return min(8, max(1, available - max(0, int(reserve_cores))))


def build_bootstrap_state(
    assignments: pd.DataFrame,
    journey_manifest: pd.DataFrame,
    decision_cells: pd.DataFrame,
    *,
    top_k: int,
    metric_states: tuple[PairwiseMetricState, ...],
) -> _BootstrapState:
    retained = journey_manifest.loc[
        journey_manifest["is_primary_eligible"], ["journey_id", "user_id"]
    ].copy()
    users = np.sort(retained["user_id"].astype(str).unique())
    user_to_index = {user_id: index for index, user_id in enumerate(users)}

    cells = decision_cells.sort_values(
        ["campaign_id", "source_date_utc", "decision_cell_id"], kind="stable"
    ).reset_index(drop=True)
    cell_ids = cells["decision_cell_id"].astype(str).to_numpy()
    cell_to_index = {cell_id: index for index, cell_id in enumerate(cell_ids)}
    if top_k >= len(cells):
        raise ScientificInvariantError(
            f"top_k={top_k} must be below cell universe={len(cells)}."
        )

    primary = assignments.loc[assignments["route_id"].isin(PRIMARY_ROUTE_ORDER)].copy()
    primary = primary.merge(retained, on="journey_id", how="left", validate="many_to_one")
    if primary["user_id"].isna().any():
        raise ScientificInvariantError("Primary route assignments contain journeys outside the cohort.")
    primary["user_index"] = primary["user_id"].astype(str).map(user_to_index)
    primary["cell_index"] = primary["decision_cell_id"].astype(str).map(cell_to_index)
    if primary[["user_index", "cell_index"]].isna().any().any():
        raise ScientificInvariantError("Bootstrap assignments fall outside user/cell indices.")

    route_matrices: dict[str, csr_matrix] = {}
    for route_id in PRIMARY_ROUTE_ORDER:
        route = primary.loc[primary["route_id"].eq(route_id)]
        matrix = csr_matrix(
            (
                route["credit_weight"].to_numpy(dtype=float),
                (
                    route["user_index"].to_numpy(dtype=np.int64),
                    route["cell_index"].to_numpy(dtype=np.int64),
                ),
            ),
            shape=(len(users), len(cells)),
            dtype=float,
        )
        route_matrices[route_id] = matrix

    expected_pairs = {
        ("arrival_time_accounting_anchor", route_id)
        for route_id in PRIMARY_SOURCE_ROUTE_ORDER
    }
    expected_pairs.update(combinations(PRIMARY_SOURCE_ROUTE_ORDER, 2))
    observed_pairs = {(item.route_left, item.route_right) for item in metric_states}
    if len(observed_pairs) != len(metric_states) or observed_pairs != expected_pairs:
        raise ScientificInvariantError(
            "Bootstrap requires exactly one frozen Kendall support for every primary comparison."
        )
    frozen_support_masks: dict[tuple[str, str], np.ndarray] = {}
    frozen_support_counts: dict[tuple[str, str], int] = {}
    for item in metric_states:
        support_ids = tuple(str(value) for value in item.support_cell_ids)
        if len(support_ids) != len(set(support_ids)):
            raise ScientificInvariantError("Frozen Kendall support contains duplicate cell IDs.")
        missing = sorted(set(support_ids).difference(cell_to_index))
        if missing:
            raise ScientificInvariantError(
                f"Frozen Kendall support contains unknown cell IDs: {missing[:10]}"
            )
        mask = np.zeros(len(cells), dtype=bool)
        mask[[cell_to_index[cell_id] for cell_id in support_ids]] = True
        if int(mask.sum()) < 2:
            raise ScientificInvariantError("Frozen Kendall support has fewer than two cells.")
        key = (item.route_left, item.route_right)
        frozen_support_masks[key] = mask
        frozen_support_counts[key] = int(mask.sum())

    return _BootstrapState(
        route_matrices=route_matrices,
        eligible_impressions=cells["eligible_impression_count"].to_numpy(dtype=float),
        tie_rank=np.arange(len(cells), dtype=np.int64),
        n_users=len(users),
        top_k=int(top_k),
        frozen_support_masks=frozen_support_masks,
        frozen_support_counts=frozen_support_counts,
    )


def build_replicate_seeds(base_seed: int, n_bootstrap: int) -> list[int]:
    seed_sequences = np.random.SeedSequence(base_seed).spawn(n_bootstrap)
    return [
        int(sequence.generate_state(1, dtype=np.uint64)[0])
        for sequence in seed_sequences
    ]

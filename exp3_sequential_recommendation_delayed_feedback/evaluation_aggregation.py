"""User-cluster weighted aggregation for immutable evaluation arrays."""
from __future__ import annotations

import numpy as np

from evaluation_artifacts import EvaluationArrays


def aggregate_user_arrays(
    arrays: EvaluationArrays,
    user_weights: np.ndarray,
    group_count: int,
    fold_count: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    shape = (len(arrays.calendar_days), group_count, fold_count, len(arrays.candidate_actions))
    source_sum = np.zeros(shape, dtype=float)
    source_count = np.zeros(shape, dtype=float)
    arrival_sum = np.zeros(shape, dtype=float)
    arrival_count = np.zeros(shape, dtype=float)
    for group_id in range(group_count):
        for fold_id in range(fold_count):
            mask = (arrays.user_group_ids == group_id) & (arrays.reference_fold_ids == fold_id)
            if not mask.any():
                continue
            weights = user_weights[mask]
            source_sum[:, group_id, fold_id] = np.tensordot(
                weights, arrays.source_target_sum[mask], axes=(0, 0)
            )
            source_count[:, group_id, fold_id] = np.tensordot(
                weights, arrays.source_target_count[mask], axes=(0, 0)
            )
            arrival_sum[:, group_id, fold_id] = np.tensordot(
                weights, arrays.arrival_target_sum[mask], axes=(0, 0)
            )
            arrival_count[:, group_id, fold_id] = np.tensordot(
                weights, arrays.arrival_target_count[mask], axes=(0, 0)
            )
    return source_sum, source_count, arrival_sum, arrival_count


_aggregate_user_arrays = aggregate_user_arrays

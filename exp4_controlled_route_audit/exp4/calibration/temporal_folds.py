"""Contiguous temporal folds with complete, non-overlapping coverage."""

from __future__ import annotations

import numpy as np


def construct_contiguous_temporal_folds(number_of_units: int, number_of_folds: int = 5) -> np.ndarray:
    if number_of_units < number_of_folds or number_of_folds < 2:
        raise ValueError("Temporal folds require at least one unit per fold")
    fold_ids = np.empty(number_of_units, dtype=np.int64)
    splits = np.array_split(np.arange(number_of_units), number_of_folds)
    for fold_id, indices in enumerate(splits):
        fold_ids[indices] = fold_id
    sizes = np.asarray([len(indices) for indices in splits], dtype=np.int64)
    if int(np.max(sizes) - np.min(sizes)) > 1:
        raise RuntimeError("Temporal fold sizes differ by more than one")
    if not np.array_equal(np.unique(fold_ids), np.arange(number_of_folds)):
        raise RuntimeError("Temporal folds do not cover every fold ID")
    for fold_id in range(number_of_folds):
        positions = np.flatnonzero(fold_ids == fold_id)
        if not np.array_equal(positions, np.arange(positions[0], positions[-1] + 1)):
            raise RuntimeError("Temporal fold is not contiguous")
    return fold_ids

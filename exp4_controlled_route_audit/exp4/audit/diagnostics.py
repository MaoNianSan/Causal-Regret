"""Selection and mask-independence diagnostics."""

from __future__ import annotations

import numpy as np


def safe_correlation(first: np.ndarray, second: np.ndarray) -> float:
    x = np.asarray(first, dtype=np.float64)
    y = np.asarray(second, dtype=np.float64)
    if x.size != y.size or x.size < 2:
        return np.nan
    if float(np.std(x)) <= 1e-14 or float(np.std(y)) <= 1e-14:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def selection_diagnostics(
    ambiguity: np.ndarray, true_defect: np.ndarray, included: np.ndarray
) -> dict[str, float]:
    included = np.asarray(included, dtype=bool)
    included_mean = float(np.mean(true_defect[included])) if np.any(included) else np.nan
    excluded_mean = float(np.mean(true_defect[~included])) if np.any(~included) else np.nan
    return {
        "ambiguity_defect_correlation": safe_correlation(ambiguity, true_defect),
        "included_mean_defect": included_mean,
        "excluded_mean_defect": excluded_mean,
        "selection_defect_difference": (
            included_mean - excluded_mean
            if np.isfinite(included_mean) and np.isfinite(excluded_mean)
            else np.nan
        ),
    }


def ambiguity_decile_records(
    replication_id: int, ambiguity: np.ndarray, true_defect: np.ndarray
) -> list[dict[str, float | int]]:
    ranks = np.argsort(np.argsort(ambiguity, kind="stable"), kind="stable")
    deciles = np.minimum(9, (10 * ranks) // len(ranks))
    records: list[dict[str, float | int]] = []
    for decile in range(10):
        mask = deciles == decile
        records.append(
            {
                "replication_id": int(replication_id),
                "ambiguity_decile": decile + 1,
                "unit_count": int(np.sum(mask)),
                "mean_ambiguity": float(np.mean(ambiguity[mask])),
                "mean_true_unit_defect": float(np.mean(true_defect[mask])),
            }
        )
    return records

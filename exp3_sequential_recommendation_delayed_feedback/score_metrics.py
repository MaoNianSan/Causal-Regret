"""Canonical score-recovery metrics and calibration source data."""
from __future__ import annotations

import numpy as np
import pandas as pd

from utilities import EPS, spearman_correlation


def assign_deciles(cell_table: pd.DataFrame) -> dict[tuple[str, str, int, str], int]:
    membership: dict[tuple[str, str, int, str], int] = {}
    for route_id in ("history_mean_control", "ridge_proxy"):
        route = cell_table[cell_table["route_id"] == route_id].copy()
        if route.empty:
            continue
        ranks = route["route_score"].rank(method="first")
        bins = pd.qcut(ranks, q=min(10, len(route)), labels=False, duplicates="drop")
        for row, decile in zip(route.itertuples(), bins):
            key = (route_id, str(row.calendar_day), int(row.user_group_id), str(row.action_id))
            membership[key] = int(decile) + 1
    return membership


def calibration_coefficients(scores: np.ndarray, targets: np.ndarray) -> tuple[float, float]:
    mask = np.isfinite(scores) & np.isfinite(targets)
    x = scores[mask]
    y = targets[mask]
    if len(x) < 2 or np.std(x) <= EPS:
        return np.nan, np.nan
    matrix = np.column_stack([np.ones(len(x)), x])
    intercept, slope = np.linalg.lstsq(matrix, y, rcond=None)[0]
    return float(intercept), float(slope)


def summarize_score_metrics(cells: pd.DataFrame) -> dict[str, float]:
    scores = cells["route_score"].to_numpy(float)
    targets = cells["heldout_target_value"].to_numpy(float)
    errors = np.abs(scores - targets)
    counts = cells["combined_target_count"].to_numpy(float).clip(min=0.0)
    centered = cells[["audit_unit_id", "route_score", "heldout_target_value"]].copy()
    centered["score_centered"] = centered["route_score"] - centered.groupby(
        "audit_unit_id"
    )["route_score"].transform("mean")
    centered["target_centered"] = centered["heldout_target_value"] - centered.groupby(
        "audit_unit_id"
    )["heldout_target_value"].transform("mean")
    intercept, slope = calibration_coefficients(scores, targets)
    spearman = spearman_correlation(scores, targets)
    mae = float(np.mean(errors))
    weighted_mae = float(np.average(errors, weights=counts)) if counts.sum() > 0 else np.nan
    return {
        "pooled_supported_cell_spearman": spearman,
        "pooled_supported_cell_mae": mae,
        "exposure_weighted_supported_cell_mae": weighted_mae,
        "within_audit_unit_centered_spearman": spearman_correlation(
            centered["score_centered"].to_numpy(float),
            centered["target_centered"].to_numpy(float),
        ),
        "calibration_intercept": intercept,
        "calibration_slope": slope,
        "score_spearman_correlation": spearman,
        "score_calibration_mae": mae,
    }


def decile_calibration_table(
    cell_table: pd.DataFrame,
    membership: dict[tuple[str, str, int, str], int] | None = None,
) -> pd.DataFrame:
    membership = membership or assign_deciles(cell_table)
    rows = []
    for route_id in ("history_mean_control", "ridge_proxy"):
        cells = cell_table[cell_table["route_id"] == route_id].copy()
        cells["calibration_decile"] = [
            membership.get(
                (route_id, str(row.calendar_day), int(row.user_group_id), str(row.action_id)),
                np.nan,
            )
            for row in cells.itertuples()
        ]
        for decile, group in cells[cells["calibration_decile"].notna()].groupby(
            "calibration_decile", sort=True
        ):
            rows.append(
                {
                    "route_id": route_id,
                    "calibration_decile": int(decile),
                    "mean_predicted_target": float(group["route_score"].mean()),
                    "mean_observed_target": float(group["heldout_target_value"].mean()),
                    "valid_action_cell_count": int(len(group)),
                }
            )
    return pd.DataFrame(rows)


_assign_deciles = assign_deciles

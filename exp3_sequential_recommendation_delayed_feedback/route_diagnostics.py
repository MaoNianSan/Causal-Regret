"""Diagnostics for route action-selection diversity and route overlap."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from utilities import save_frame, save_json


def summarize_route_selection(unit_metrics: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    required = {"route_id", "route_selected_action_id", "audit_unit_id", "selection_fold_id"}
    missing = required.difference(unit_metrics.columns)
    if missing:
        raise ValueError(f"Route-selection diagnostics missing columns: {sorted(missing)}")
    route_rows: list[dict[str, object]] = []
    for route_id, group in unit_metrics.groupby("route_id", sort=True):
        counts = group["route_selected_action_id"].astype(str).value_counts()
        total = int(counts.sum())
        probabilities = counts.to_numpy(float) / total if total else np.array([], dtype=float)
        entropy = float(-(probabilities * np.log(probabilities)).sum()) if probabilities.size else np.nan
        route_rows.append(
            {
                "route_id": str(route_id),
                "selection_direction_count": total,
                "unique_selected_action_count": int(len(counts)),
                "dominant_selected_action_id": str(counts.index[0]) if total else "",
                "dominant_selected_action_share": float(counts.iloc[0] / total) if total else np.nan,
                "maximum_selected_action_share": float(counts.iloc[0] / total) if total else np.nan,
                "selected_action_entropy": entropy,
                "all_directions_same_action": bool(len(counts) == 1),
            }
        )
    summary = pd.DataFrame(route_rows)

    keys = ["audit_unit_id", "selection_fold_id"]
    pivot = unit_metrics.pivot_table(
        index=keys,
        columns="route_id",
        values="route_selected_action_id",
        aggfunc="first",
    )
    comparable = pivot.dropna(subset=["history_mean_control", "ridge_proxy"]) if {
        "history_mean_control", "ridge_proxy"
    }.issubset(pivot.columns) else pd.DataFrame()
    match_rate = (
        float((comparable["history_mean_control"] == comparable["ridge_proxy"]).mean())
        if len(comparable)
        else np.nan
    )
    contrast = {
        "comparison_id": "ridge_proxy_vs_history_mean_control",
        "comparable_selection_direction_count": int(len(comparable)),
        "selected_action_match_rate": match_rate,
        "selected_action_difference_rate": 1.0 - match_rate if np.isfinite(match_rate) else np.nan,
        "complete_selection_equivalence": bool(np.isfinite(match_rate) and np.isclose(match_rate, 1.0)),
    }
    summary["ridge_history_selected_action_agreement"] = match_rate
    return summary, contrast


def write_route_selection_diagnostics(unit_metrics: pd.DataFrame, output_dir: Path) -> None:
    summary, contrast = summarize_route_selection(unit_metrics)
    save_frame(summary, output_dir / "diagnostics" / "exp3_route_selection_diagnostics.csv")
    save_json(contrast, output_dir / "diagnostics" / "exp3_ridge_history_selection_overlap.json")

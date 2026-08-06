"""Frozen-table preparation and rendering for the full-design support appendix."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


READY_COLOR = "#2A7F62"
LIMITED_COLOR = "#9C3D35"
ACTION_COLOR = "#4C72B0"


def candidate_labels(vocabulary: pd.DataFrame) -> pd.DataFrame:
    required = {"action_id", "action_display_name", "is_candidate_action"}
    missing = required.difference(vocabulary.columns)
    if missing:
        raise ValueError(f"Action vocabulary is missing columns: {sorted(missing)}")
    candidate = vocabulary.copy()
    candidate["is_candidate_action"] = candidate["is_candidate_action"].astype(
        str
    ).str.lower().isin({"true", "1"})
    return candidate[candidate["is_candidate_action"]][
        ["action_id", "action_display_name"]
    ].drop_duplicates("action_id")


def prepare_full_support_preflight(
    action_summary: pd.DataFrame,
    preflight_summary: pd.DataFrame,
    action_space_coverage: pd.DataFrame,
    vocabulary: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = {
        "action_id",
        "supported_unit_rate",
        "minimum_fold_count_p10",
        "minimum_fold_count_median",
        "minimum_fold_count_p90",
    }
    missing = required.difference(action_summary.columns)
    if missing:
        raise ValueError(f"Full-design action support file is missing columns: {sorted(missing)}")
    actions = action_summary.merge(
        candidate_labels(vocabulary), on="action_id", how="left", validate="one_to_one"
    )
    if actions["action_display_name"].isna().any():
        raise ValueError("Full-design support actions are missing display labels")
    actions = actions.sort_values(
        ["minimum_fold_count_median", "action_id"], kind="stable"
    ).reset_index(drop=True)
    actions["action_rank"] = np.arange(1, len(actions) + 1)

    evaluation = preflight_summary[preflight_summary["split_id"] == "evaluation"]
    if len(evaluation) != 1:
        raise ValueError("Full-design preflight must contain one displayed evaluation summary")
    row = evaluation.iloc[0]
    mass = action_space_coverage[
        (action_space_coverage["split_id"] == "evaluation")
        & (action_space_coverage["design_scope"] == "full_design_preflight")
    ]
    if len(mass) != 1:
        raise ValueError("Action-space coverage must contain one evaluation full-design row")
    metrics = pd.DataFrame(
        [
            {
                "metric_id": "action_coverage",
                "display_name": "Action support",
                "value": float(row["action_coverage"]),
            },
            {
                "metric_id": "reference_pair_coverage",
                "display_name": "Reference-pair support",
                "value": float(row.get("reference_pair_coverage", row["pair_coverage"])),
            },
            {
                "metric_id": "audit_unit_coverage",
                "display_name": "Valid units",
                "value": float(row["audit_unit_coverage"]),
            },
            {
                "metric_id": "exposure_mass_coverage",
                "display_name": "Exposure mass",
                "value": float(mass.iloc[0]["selected_action_exposure_mass_coverage"]),
            },
        ]
    )
    if not np.isfinite(metrics["value"]).all() or (
        (metrics["value"] < 0) | (metrics["value"] > 1)
    ).any():
        raise ValueError("Full-design coverage metrics must lie in [0, 1]")
    return actions, metrics


def draw_full_support_preflight(
    actions: pd.DataFrame,
    metrics: pd.DataFrame,
    threshold: int,
    group_count: int,
    status: str,
) -> plt.Figure:
    height = max(4.4, 2.7 + 0.20 * len(actions))
    figure = plt.figure(figsize=(7.5, height))
    grid = figure.add_gridspec(1, 2, width_ratios=[1.75, 0.80], wspace=0.62)
    ax_actions = figure.add_subplot(grid[0, 0])
    ax_metrics = figure.add_subplot(grid[0, 1])

    y = np.arange(len(actions), dtype=float)
    low = actions["minimum_fold_count_p10"].to_numpy(float)
    median = actions["minimum_fold_count_median"].to_numpy(float)
    high = actions["minimum_fold_count_p90"].to_numpy(float)
    rates = actions["supported_unit_rate"].to_numpy(float)
    ax_actions.hlines(y, low, high, linewidth=1.8, color=ACTION_COLOR)
    ax_actions.scatter(
        median,
        y,
        s=25,
        c=[READY_COLOR if rate >= 0.8 else LIMITED_COLOR for rate in rates],
        zorder=3,
    )
    ax_actions.axvline(threshold, linestyle="--", linewidth=1.0, color="0.35")
    labels = []
    for display, rate in zip(actions["action_display_name"].astype(str), rates):
        short = display if len(display) <= 20 else display[:17] + "..."
        labels.append(f"{short} ({rate:.0%})")
    ax_actions.set_yticks(y, labels)
    ax_actions.invert_yaxis()
    ax_actions.set_xlabel("Minimum events per fold (median; 10-90% range)")
    ax_actions.set_title("(a) Full-design cell support by action", loc="left", fontweight="semibold")
    ax_actions.grid(axis="x", alpha=0.18)

    y2 = np.arange(len(metrics), dtype=float)
    values = metrics["value"].to_numpy(float)
    ax_metrics.hlines(y2, 0, values, color="0.72", linewidth=2.0)
    ax_metrics.scatter(
        values,
        y2,
        s=35,
        c=[READY_COLOR if value >= 0.8 else LIMITED_COLOR for value in values],
        zorder=3,
    )
    ax_metrics.axvline(0.8, linestyle="--", linewidth=1.0, color="0.35")
    ax_metrics.set_xlim(0, 1.03)
    ax_metrics.set_yticks(y2, metrics["display_name"].astype(str))
    ax_metrics.invert_yaxis()
    ax_metrics.set_xlabel("Coverage")
    ax_metrics.set_title(
        f"(b) Readiness and scope\nG={group_count}; threshold={threshold}/fold",
        loc="left",
        fontweight="semibold",
    )
    ax_metrics.grid(axis="x", alpha=0.18)
    for value, yy in zip(values, y2):
        ax_metrics.text(min(value + 0.025, 1.0), yy, f"{value:.0%}", va="center", fontsize=7)
    ax_metrics.text(0.02, -0.09, f"Status: {status}", transform=ax_metrics.transAxes, fontsize=7, va="top")
    figure.subplots_adjust(left=0.15, right=0.98, top=0.91, bottom=0.13)
    return figure


_candidate_labels = candidate_labels
_prepare_full_support_preflight = prepare_full_support_preflight
_draw_full_support_preflight = draw_full_support_preflight

"""Logged-supported ranking column of the Exp3 main figure."""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from plot_contract import COLORS, MAIN_FIGURE_RANKING_METRICS, draw_route_metric, validated_range


def draw_ranking_panels(
    top: plt.Axes,
    bottom: plt.Axes,
    primary: pd.DataFrame,
    paired: pd.DataFrame,
) -> list[dict[str, object]]:
    rows = draw_route_metric(
        top,
        primary,
        MAIN_FIGURE_RANKING_METRICS[0],
        "Agreement (higher is better)",
        show_labels=False,
    )
    contrast = paired.iloc[0]
    point = float(contrast["full_sample_estimate"])
    median = float(contrast["resampling_median"])
    low, high = validated_range(
        float(contrast["sensitivity_lower"]), float(contrast["sensitivity_upper"])
    )
    color = COLORS["ridge_proxy"]
    bottom.axvline(0.0, color="0.45", linestyle="--", linewidth=0.8)
    bottom.hlines(0.0, low, high, color=color, linewidth=1.7, alpha=0.7)
    bottom.plot(median, 0.0, marker="D", markerfacecolor="white", markeredgecolor=color)
    bottom.plot(point, 0.0, marker="D", color=color)
    span = max(high - low, abs(point), abs(median), 1e-6)
    bottom.set_xlim(min(low, point, median, 0.0) - 0.15 * span, max(high, point, median, 0.0) + 0.15 * span)
    bottom.set_yticks([0.0], ["Ridge vs Historical"])
    bottom.set_xlabel("Paired value gain (positive favors Ridge)")
    bottom.grid(axis="x", alpha=0.18, linewidth=0.6)
    top.set_title("(c) Logged-supported ranking recovery", loc="left", fontweight="semibold")
    for row in rows:
        row["panel_id"] = "panel_c_ranking"
    rows.append(
        {
            "panel_id": "panel_c_ranking",
            "contrast_id": contrast["contrast_id"],
            "metric_id": MAIN_FIGURE_RANKING_METRICS[1],
            "full_sample_estimate": point,
            "resampling_median": median,
            "sensitivity_lower": low,
            "sensitivity_upper": high,
        }
    )
    return rows

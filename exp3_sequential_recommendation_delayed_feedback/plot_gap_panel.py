"""Held-out reference-pair gap column of the Exp3 main figure."""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from plot_contract import MAIN_FIGURE_GAP_METRICS, draw_route_metric


def draw_gap_panels(
    top: plt.Axes,
    bottom: plt.Axes,
    primary: pd.DataFrame,
) -> list[dict[str, object]]:
    rows = draw_route_metric(
        top,
        primary,
        MAIN_FIGURE_GAP_METRICS[0],
        "Maximum error (lower is better)",
        show_labels=False,
        include_zero=True,
    )
    rows += draw_route_metric(
        bottom,
        primary,
        MAIN_FIGURE_GAP_METRICS[1],
        "Sign agreement (higher is better)",
        show_labels=False,
    )
    top.set_title("(b) Held-out reference-pair gap recovery", loc="left", fontweight="semibold")
    for row in rows:
        row["panel_id"] = "panel_b_gap"
    return rows

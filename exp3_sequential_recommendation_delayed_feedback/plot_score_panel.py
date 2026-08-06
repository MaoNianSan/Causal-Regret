"""Score-recovery column of the Exp3 main figure."""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from plot_contract import MAIN_FIGURE_SCORE_METRICS, draw_route_metric


def draw_score_panels(
    top: plt.Axes,
    bottom: plt.Axes,
    primary: pd.DataFrame,
) -> list[dict[str, object]]:
    rows = draw_route_metric(
        top,
        primary,
        MAIN_FIGURE_SCORE_METRICS[0],
        "Spearman (higher is better)",
        show_labels=True,
    )
    rows += draw_route_metric(
        bottom,
        primary,
        MAIN_FIGURE_SCORE_METRICS[1],
        "MAE (lower is better)",
        show_labels=True,
    )
    top.set_title("(a) Score recovery on common logged support", loc="left", fontweight="semibold")
    for row in rows:
        row["panel_id"] = "panel_a_score"
    return rows

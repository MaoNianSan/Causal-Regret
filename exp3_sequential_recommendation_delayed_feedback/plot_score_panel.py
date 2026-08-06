"""Score-recovery column of the Exp3 main figure."""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from plot_contract import draw_route_metric


def draw_score_panels(
    top: plt.Axes,
    bottom: plt.Axes,
    primary: pd.DataFrame,
) -> list[dict[str, object]]:
    rows = draw_route_metric(
        top,
        primary,
        "pooled_supported_cell_spearman",
        "Spearman (higher is better)",
        show_labels=True,
    )
    rows += draw_route_metric(
        bottom,
        primary,
        "pooled_supported_cell_mae",
        "MAE (lower is better)",
        show_labels=True,
    )
    top.set_title("(a) Score recovery on common logged support", loc="left", fontweight="semibold")
    for row in rows:
        row["panel_id"] = "panel_a_score"
    return rows

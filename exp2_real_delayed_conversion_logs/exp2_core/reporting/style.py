from __future__ import annotations

import math
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def set_publication_style(config: dict[str, Any]) -> None:
    plots = config["plots"]
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": float(plots["tick_font_size"]),
            "axes.labelsize": float(plots["axis_label_font_size"]),
            "axes.titlesize": float(plots["axis_label_font_size"]),
            "xtick.labelsize": float(plots["tick_font_size"]),
            "ytick.labelsize": float(plots["tick_font_size"]),
            "legend.fontsize": float(plots["annotation_font_size"]),
            "axes.linewidth": 0.8,
            "lines.linewidth": float(plots["line_width"]),
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def dynamic_tv_upper(values: pd.Series | np.ndarray, *, minimum: float = 0.15) -> float:
    numeric = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    maximum = float(numeric.max()) if not numeric.empty else 0.0
    return round(min(1.0, max(minimum, math.ceil(maximum / 0.05) * 0.05)), 2)


def shared_count(value: float, top_k: int) -> int:
    return int(np.clip(np.rint(float(value) * int(top_k)), 0, int(top_k)))


def shared_annotation(
    point: float, lower: float, upper: float, top_k: int, *, compact: bool = False
) -> str:
    prefix = "Shared" if compact else f"Top-{top_k} shared"
    return (
        f"{prefix}: {shared_count(point, top_k)}/{top_k} "
        f"[{shared_count(lower, top_k)}, {shared_count(upper, top_k)}]"
    )

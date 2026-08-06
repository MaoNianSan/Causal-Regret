"""Shared paper figure style."""

from __future__ import annotations

import matplotlib.pyplot as plt


AUDIT_COLORS = {
    "mcar_unweighted": "#2F6B9A",
    "ambiguity_selective_unweighted": "#C75B39",
    "ambiguity_selective_ipw": "#3D8B6D",
}
AUDIT_MARKERS = {
    "mcar_unweighted": "o",
    "ambiguity_selective_unweighted": "s",
    "ambiguity_selective_ipw": "^",
}
NOISE_COLORS = {0.0: "#454545", 0.10: "#2F6B9A", 0.25: "#B07A1B", 1.0: "#A63D5D"}
NOISE_MARKERS = {0.0: "o", 0.10: "s", 0.25: "^", 1.0: "v"}


def set_publication_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 7.2,
            "axes.labelsize": 8.0,
            "axes.titlesize": 8.2,
            "xtick.labelsize": 7.0,
            "ytick.labelsize": 7.0,
            "legend.fontsize": 6.7,
            "axes.linewidth": 0.8,
            "grid.linewidth": 0.5,
            "grid.alpha": 0.24,
            "savefig.bbox": "tight",
        }
    )

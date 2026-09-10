#!/usr/bin/env python
"""Supplementary evidence already present in the frozen outputs.

Produces two figures that the frozen pipeline computed but the manuscript did
not present:

  * Exp2 attribution-entropy stratification: the credit-dispersion entropy of
    each source-time route within candidate-source strata.
  * Exp1 horizon scaling: the learner-level structural-regret rate as a function
    of horizon, under arrival-clock versus source-round factual-feedback binding.

Reuses frozen outputs only.

Run from the repository root:
    ./.venv/Scripts/python.exe extra_evidence.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from presentation.common import PALETTE, configure_matplotlib  # noqa: E402

EXP2_AMBIG = ROOT / (
    "exp2_real_delayed_conversion_logs/outputs/exp2-full-20260807T111616+0800/"
    "derived/ambiguity_mechanism.csv"
)
EXP1_HORIZON = ROOT / (
    "exp1_alignment_transfer/outputs/full/targeted/exp1_targeted_horizon_summary.csv"
)
OUT = ROOT / "publication" / "extra_evidence"

STRATA = ["candidate_cells_1", "candidate_cells_2", "candidate_cells_3plus"]
STRATUM_LABEL = {
    "candidate_cells_1": "1",
    "candidate_cells_2": "2",
    "candidate_cells_3plus": r"$\geq 3$",
}
ROUTES = {
    "linear_source_cell_credit": ("Linear", PALETTE["blue_main"]),
    "time_decay_source_cell_credit": ("Time-decay", PALETTE["blue_secondary"]),
}


def main() -> int:
    configure_matplotlib()
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- Panel A: Exp2 attribution entropy ----
    entropy = {route: [] for route in ROUTES}
    with EXP2_AMBIG.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["record_type"] != "route_assignment_shape":
                continue
            route = row["route_id"]
            if route in ROUTES and row["mean_assignment_entropy"]:
                entropy[route].append(
                    (row["ambiguity_stratum"], float(row["mean_assignment_entropy"]))
                )
    for route in ROUTES:
        entropy[route] = sorted(
            entropy[route], key=lambda item: STRATA.index(item[0])
        )

    # ---- Panel B: Exp1 horizon scaling ----
    horizon: dict[str, dict[int, float]] = {"arrival_clock": {}, "source_round": {}}
    with EXP1_HORIZON.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["metric_id"] != "structural_regret_rate":
                continue
            binding = row["feedback_binding_id"]
            if binding in horizon:
                horizon[binding][int(row["target_horizon"])] = float(row["estimate"])

    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.8), constrained_layout=True)

    ax = axes[0]
    width = 0.36
    xs = np.arange(len(STRATA))
    for index, (route, (label, color)) in enumerate(ROUTES.items()):
        values = [value for _, value in entropy[route]]
        ax.bar(
            xs + (index - 0.5) * width,
            values,
            width,
            color=color,
            edgecolor="black",
            linewidth=0.8,
            label=label,
        )
        for x, value in zip(xs + (index - 0.5) * width, values):
            ax.text(x, value + 0.03, f"{value:.2f}", ha="center", va="bottom", fontsize=6.5)
    ax.set_xticks(xs, [STRATUM_LABEL[s] for s in STRATA])
    ax.set_xlabel("Candidate source cells")
    ax.set_ylabel("Mean assignment entropy")
    ax.set_title("(a) Attribution entropy")
    ax.legend(loc="upper left")
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1]
    styles = {
        "arrival_clock": ("Arrival-clock", PALETTE["red_strong"], "o"),
        "source_round": ("Source-round", PALETTE["blue_main"], "s"),
    }
    for binding, (label, color, marker) in styles.items():
        ts = sorted(horizon[binding])
        ys = [horizon[binding][t] for t in ts]
        ax.plot(ts, ys, marker=marker, color=color, label=label, markersize=4.5)
    ax.set_xscale("log")
    ax.set_xticks([1000, 5000, 10000], ["1k", "5k", "10k"])
    ax.set_xlabel(r"Horizon $T$")
    ax.set_ylabel(r"Structural-regret rate $R_T^c/T$")
    ax.set_title("(b) Horizon scaling")
    ax.legend(loc="center right")
    ax.grid(alpha=0.25)

    fig.savefig(OUT / "fig_extra_evidence.pdf")
    fig.savefig(OUT / "fig_extra_evidence.png", dpi=300)
    plt.close(fig)

    print("entropy (Linear):", [f"{v:.4f}" for _, v in entropy["linear_source_cell_credit"]])
    for binding in styles:
        ts = sorted(horizon[binding])
        print(binding, {t: round(horizon[binding][t], 4) for t in ts})
    print(f"written: {OUT / 'fig_extra_evidence.pdf'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

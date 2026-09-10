#!/usr/bin/env python
"""Exponent / margin-threshold verification for Propositions 4.5-4.7.

Reuses frozen outputs only (no experiment is rerun):
  * Exp1 targeted margin-threshold sweep -> threshold behaviour of Prop 4.5(2)
    (chi = 0 iff delta < mu), observed vs the closed-form ``expected_chi``.
  * Exp4 controlled route grid -> log-log scaling of the pairwise sign
    disagreement rate rho against the alignment-budget rate A_T/T, compared
    with the kappa/(kappa+1) form of Prop 4.6.

Run from the repository root:
    ./.venv/Scripts/python.exe exponent_check.py
"""
from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from presentation.common import PALETTE, configure_matplotlib  # noqa: E402

EXP1_SWEEP = ROOT / (
    "exp1_alignment_transfer/outputs/full/targeted/"
    "exp1_targeted_theory_margin_threshold_sweep.csv"
)
EXP4_SUMMARY = ROOT / (
    "exp4_controlled_route_audit/outputs/runs/full_20260817T071019Z_7d7146b7/"
    "derived/module_a/exp4_module_a_population_summary.csv"
)
OUT = ROOT / "publication" / "exponent_check"


def loglog_slope(xs: list[float], ys: list[float]) -> float:
    lx = [math.log(v) for v in xs]
    ly = [math.log(v) for v in ys]
    n = len(lx)
    mx = sum(lx) / n
    my = sum(ly) / n
    return sum((a - mx) * (b - my) for a, b in zip(lx, ly)) / sum(
        (a - mx) ** 2 for a in lx
    )


def main() -> int:
    configure_matplotlib()

    # ---- Source 1: Exp1 margin-threshold sweep (Prop 4.5 threshold) ----
    by_ratio: dict[float, dict[str, list[float]]] = defaultdict(
        lambda: {"chi": [], "rho": [], "exp": []}
    )
    with EXP1_SWEEP.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = float(row["ratio"])
            by_ratio[key]["chi"].append(float(row["mean_chi"]))
            by_ratio[key]["rho"].append(float(row["mean_rho"]))
            by_ratio[key]["exp"].append(float(row["expected_chi"]))
    ratios = sorted(by_ratio)
    chi = [sum(by_ratio[k]["chi"]) / len(by_ratio[k]["chi"]) for k in ratios]
    exp_chi = [sum(by_ratio[k]["exp"]) / len(by_ratio[k]["exp"]) for k in ratios]
    max_dev = max(abs(a - b) for a, b in zip(chi, exp_chi))

    # ---- Source 2: Exp4 (A_T/T, rho) scaling (Prop 4.6 rate) ----
    xs: list[float] = []
    ys: list[float] = []
    with EXP4_SUMMARY.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["route_id"] != "proxy_label":
                continue
            x = float(row["population_action_gap_defect_mean"])
            y = float(row["pairwise_gap_sign_disagreement_rate_mean"])
            if x > 0:
                xs.append(x)
                ys.append(y)
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    xs = [xs[i] for i in order]
    ys = [ys[i] for i in order]
    slope = loglog_slope(xs, ys)

    # ---- Figure ----
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.8), constrained_layout=True)

    ax = axes[0]
    ax.plot(ratios, chi, "o-", color=PALETTE["blue_main"], label="Observed")
    ax.plot(
        ratios,
        exp_chi,
        "--",
        color=PALETTE["red_strong"],
        label="Closed-form (Prop. 4.5)",
    )
    ax.axvline(1.0, color=PALETTE["neutral_dark"], linewidth=0.9, linestyle=":")
    ax.set_xlabel(r"Alignment defect ratio $\delta_t^r/\mu_t^c$")
    ax.set_ylabel(r"Choice disagreement $\overline{\chi}_T^r$")
    ax.set_title("(a) Margin threshold")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.25)

    ax = axes[1]
    ax.loglog(xs, ys, "o", color=PALETTE["blue_main"], label="Exp4 grid")
    x0, x1 = min(xs), max(xs)
    a0 = ys[0] / xs[0] ** slope
    ax.loglog(
        [x0, x1],
        [a0 * x0**slope, a0 * x1**slope],
        "-",
        color=PALETTE["red_strong"],
        label=rf"fit: slope $={slope:.2f}$",
    )
    ax.loglog(
        [x0, x1],
        [ys[0] * (x0 / xs[0]), ys[0] * (x1 / xs[0])],
        "--",
        color=PALETTE["neutral_dark"],
        label=r"slope $=1$",
    )
    ax.set_xlabel(r"Alignment-budget rate $\mathfrak{A}_T^r/T$")
    ax.set_ylabel(r"Pairwise sign disagreement $\overline{\rho}_T^r$")
    ax.set_title(r"(b) Rate $\overline{\rho}_T^r\sim(\mathfrak{A}_T^r/T)^{\kappa/(\kappa+1)}$")
    ax.legend(loc="upper left")
    ax.grid(True, which="both", alpha=0.2)

    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "fig_exponent_check.pdf")
    fig.savefig(OUT / "fig_exponent_check.png", dpi=300)
    plt.close(fig)

    print(f"margin-threshold max |observed - closed-form| = {max_dev:.3e}")
    print(f"log-log slope (rho vs A_T/T) = {slope:.4f}  ->  kappa ~ {slope / (1 - slope):.2f}")
    print(f"written: {OUT / 'fig_exponent_check.pdf'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

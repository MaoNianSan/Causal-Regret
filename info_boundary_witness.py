#!/usr/bin/env python
"""Information-boundary witness for Corollary 4.14.

Simulates the two-world witness of Theorem 4.12 with independent source-label
retention ``p_src`` and records the minimax absolute-error risk by Monte Carlo.
The closed form is

    R*(p_src) = (Delta_Theta / 2) * (1 - p_src)**(n * T).

This is a self-contained numerical check; no experiment in the repository is
rerun.

Run from the repository root:
    ./.venv/Scripts/python.exe info_boundary_witness.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from presentation.common import PALETTE, configure_matplotlib  # noqa: E402

OUT = ROOT / "publication" / "info_boundary_witness"
DELTA = 1.0
N_TRAJ = 1
REPS = 200_000
P_GRID = (0.0, 0.1, 0.3, 0.5)
T_GRID = np.arange(1, 21)


def risk_mc(p_src: float, horizon: int, rng: np.random.Generator) -> float:
    """Monte Carlo minimax risk: a single revealed world-separating label suffices."""
    retained = rng.random((REPS, horizon)) < p_src
    ambiguous = ~retained.any(axis=1)
    return (DELTA / 2.0) * float(ambiguous.mean())


def main() -> int:
    configure_matplotlib()
    rng = np.random.default_rng(0)

    fig, ax = plt.subplots(figsize=(3.5, 2.8), constrained_layout=True)
    shades = {
        0.0: PALETTE["red_strong"],
        0.1: PALETTE["neutral_dark"],
        0.3: PALETTE["blue_secondary"],
        0.5: PALETTE["blue_main"],
    }
    max_dev = 0.0
    for p_src in P_GRID:
        mc = np.array([risk_mc(p_src, int(T), rng) for T in T_GRID])
        theory = (DELTA / 2.0) * (1.0 - p_src) ** (N_TRAJ * T_GRID)
        max_dev = max(max_dev, float(np.max(np.abs(mc - theory))))
        ax.semilogy(
            T_GRID,
            theory,
            "-",
            color=shades[p_src],
            label=rf"$p_{{\mathrm{{src}}}}={p_src}$",
        )
        ax.semilogy(T_GRID, mc, "o", color=shades[p_src], markersize=3.2)
    ax.set_xlabel(r"Horizon $T$")
    ax.set_ylabel(r"Minimax risk $\mathcal{R}^{\star}_{n,T}(p_{\mathrm{src}})$")
    ax.set_title("Witness-level identification rate")
    ax.legend(loc="lower left")
    ax.grid(True, which="both", alpha=0.2)

    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "fig_info_boundary_witness.pdf")
    fig.savefig(OUT / "fig_info_boundary_witness.png", dpi=300)
    plt.close(fig)

    print(f"max |MC - closed form| over grid = {max_dev:.3e}")
    print(f"written: {OUT / 'fig_info_boundary_witness.pdf'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

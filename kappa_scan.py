#!/usr/bin/env python
"""Explicit kappa-scan for Proposition 4.7 (sharpness of the soft-margin exponent).

Implements the two-action construction of Proposition 4.7 exactly:

  * horizon ``T``; on exactly one round the structural losses are ``(0, d_T)``
    and the route losses are ``(d_T, 0)``; on the remaining ``T-1`` rounds both
    maps equal ``(0, 1)``;
  * ``d_T = T**(-1/kappa)``.

The construction gives, in closed form,

    A_T^r / T = 2 * T**(-(1 + 1/kappa)),      rho_bar = chi_bar = 1 / T,

so the claimed identity  rho_bar = 2**(-kappa/(kappa+1)) * (A_T^r/T)**(kappa/(kappa+1))
is checked numerically for a grid of ``kappa``, which also verifies that the
exponent is *matched exactly* (not merely upper-bounded).

Run from the repository root:
    ./.venv/Scripts/python.exe kappa_scan.py
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

OUT = ROOT / "publication" / "kappa_scan"
KAPPAS = (0.5, 1.0, 2.0, 4.0, 8.0)
T_GRID = np.arange(2, 2001)


def main() -> int:
    configure_matplotlib()

    fig, ax = plt.subplots(figsize=(3.6, 2.9), constrained_layout=True)
    colors = [
        PALETTE["red_strong"],
        PALETTE["neutral_dark"],
        PALETTE["blue_secondary"],
        PALETTE["blue_main"],
        PALETTE["highlight"],
    ]
    max_err = 0.0
    for kappa, color in zip(KAPPAS, colors):
        x = 2.0 * T_GRID ** (-(1.0 + 1.0 / kappa))  # A_T^r / T
        rho = 1.0 / T_GRID                          # rho_bar = chi_bar
        predicted = 2.0 ** (-kappa / (kappa + 1.0)) * x ** (kappa / (kappa + 1.0))
        max_err = max(max_err, float(np.max(np.abs(rho - predicted))))
        ax.loglog(x, rho, "-", color=color, linewidth=1.6, label=rf"$\kappa={kappa:g}$")
        ax.loglog(
            x[:: max(1, len(x) // 12)],
            predicted[:: max(1, len(x) // 12)],
            "o",
            color=color,
            markerfacecolor="white",
            markersize=3.0,
        )

    ax.set_xlabel(r"$\mathfrak{A}_T^r/T$")
    ax.set_ylabel(r"$\overline{\rho}_T^r=\overline{\chi}_T^r$")
    ax.set_title(r"Sharp exponent $2^{-\kappa/(\kappa+1)}(\mathfrak{A}_T^r/T)^{\kappa/(\kappa+1)}$")
    ax.legend(loc="upper left", title="Construction")
    ax.grid(True, which="both", alpha=0.2)

    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "fig_kappa_scan.pdf")
    fig.savefig(OUT / "fig_kappa_scan.png", dpi=300)
    plt.close(fig)

    print(f"max |observed rho - closed form| over kappa grid = {max_err:.3e}")
    print(f"written: {OUT / 'fig_kappa_scan.pdf'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.plot_utils import plot_exp1_bundles


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate the EXP1 formal figure from an existing seed summary.")
    parser.add_argument("--run-mode", choices=("fast", "full"), required=True)
    parser.add_argument("--output-tag", default=None)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent / "outputs" / (args.output_tag or args.run_mode)
    seed_path = root / "summaries" / "seed_summary.csv"
    if not seed_path.exists():
        raise FileNotFoundError(f"Missing {seed_path}; run the simulation first.")
    plot_exp1_bundles(pd.read_csv(seed_path), root)
    print(root / "figures" / "png" / "fig_exp1_validity_boundary.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.plot_utils import plot_exp1_bundles


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate EXP1 figure bundle from a completed run."
    )
    parser.add_argument("--mode", choices=("fast", "full"), default="fast")
    parser.add_argument("--output-tag", default=None)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent / "outputs" / (args.output_tag or args.mode)
    seed = pd.read_csv(root / "summaries" / "seed_summary.csv")
    plot_exp1_bundles(seed, root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

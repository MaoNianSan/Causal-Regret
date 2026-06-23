from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.plot_utils import plot_validity_boundary
from src.runner import _make_summaries


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild summaries and formal figure from an existing raw seed-level result file.")
    parser.add_argument("--mode", choices=("fast", "full"), default="fast")
    parser.add_argument("--output-tag", default=None)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent / "outputs" / (args.output_tag or args.mode)
    raw = root / "raw" / "seed_level_results.csv"
    if not raw.exists():
        raise FileNotFoundError(f"Missing {raw}; run the simulation first.")
    seed = pd.read_csv(raw)
    _make_summaries(seed, root)
    plot_validity_boundary(seed, root)
    print(f"Rebuilt summaries and figure under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

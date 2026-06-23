"""Compatibility entry point for rebuilding EXP1 summaries from completed raw results.

The former module reconstructed an obsolete estimand and obsolete scenario names.
The revised runner is the sole source of aggregation logic.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.plot_utils import plot_exp1_bundles
from src.runner import _make_summaries


def rebuild(output_root: str | Path) -> None:
    root = Path(output_root)
    raw = root / "raw" / "seed_level_results.csv"
    if not raw.exists():
        raise FileNotFoundError(f"Missing {raw}")
    seed = pd.read_csv(raw)
    _make_summaries(seed, root)
    plot_exp1_bundles(seed, root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    rebuild(args.output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

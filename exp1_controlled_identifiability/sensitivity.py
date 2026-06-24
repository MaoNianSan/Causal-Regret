"""Post-run sensitivity extractor for the revised EXP1 design.

This script does not silently rerun an obsolete scenario grid.  It extracts
pre-registered sensitivity-relevant quantities (label rate, proxy quality,
matched delay, attribution diagnostics) from a completed run.  New sweeps should
be launched explicitly with a distinct output tag and recorded in the manifest.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("fast", "full"), default="full")
    parser.add_argument("--output-tag", default=None)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent / "outputs" / (args.output_tag or args.mode)
    source = root / "summaries" / "seed_summary.csv"
    if not source.exists():
        raise FileNotFoundError(f"Missing {source}; run the design first.")
    seed = pd.read_csv(source)
    columns = [
        c
        for c in [
            "seed",
            "delay_setting",
            "regime",
            "method",
            "final_Rc",
            "mean_delay",
            "soft_attribution_true_mass",
            "soft_attribution_top1_accuracy",
            "proxy_state_error_mean",
            "assignment_entropy",
            "ranking_reversal_rate",
        ]
        if c in seed.columns
    ]
    out = seed.loc[:, columns].copy()
    dest = root / "summaries" / "sensitivity_extract.csv"
    out.to_csv(dest, index=False)
    print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

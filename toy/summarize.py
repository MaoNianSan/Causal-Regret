#!/usr/bin/env python3
"""Regenerate Toy summaries and figures from valid run outputs.

The runner already writes all summary files. This utility is retained for
post-processing and preserves the same schema when rebuilding fast-mode
trajectories from raw step logs.
"""
from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from io_utils import ensure_dir
from main import _method_summary_rows
from plot import generate_figures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate Toy summaries and figures.")
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--mode", choices=["fast", "full"], default="full")
    return parser.parse_args()


def resolve_output_dir(base: Path, output_dir: str, mode: str) -> Path:
    candidate = Path(output_dir)
    return ((candidate if candidate.is_absolute() else base / candidate) / mode).resolve()


def main() -> None:
    args = parse_args()
    root = resolve_output_dir(Path(__file__).resolve().parent, args.output_dir, args.mode)
    summary_dir = ensure_dir(root / "summary")
    seed_path = summary_dir / "toy_seed_summary.csv"
    if not seed_path.exists() or seed_path.stat().st_size == 0:
        raise FileNotFoundError(f"Missing seed summary: {seed_path}")

    seed_df = pd.read_csv(seed_path)
    seed_rows = seed_df.to_dict(orient="records")
    method_rows = _method_summary_rows(seed_rows)
    pd.DataFrame(method_rows).to_csv(summary_dir / "toy_method_summary.csv", index=False)

    step_path = root / "raw" / "step_log.csv"
    if step_path.exists() and step_path.stat().st_size > 0:
        step_df = pd.read_csv(step_path)
        required = {"delay_setting", "method", "t", "cumulative_causal_regret"}
        missing = required.difference(step_df.columns)
        if missing:
            raise ValueError(f"Step log missing columns: {sorted(missing)}")
        experiment_id = str(seed_df["experiment_id"].iloc[0])
        mode = str(seed_df["mode"].iloc[0])
        config_hash = str(seed_df["config_hash"].iloc[0])
        grouped = step_df.groupby(["delay_setting", "method", "t"])["cumulative_causal_regret"]
        trajectory_rows = []
        for (delay_setting, method, t), series in grouped:
            values = series.to_numpy(dtype=float)
            n = len(values)
            mean = float(values.mean())
            se = float(values.std(ddof=1) / math.sqrt(n)) if n > 1 else 0.0
            trajectory_rows.append(
                {
                    "experiment_id": experiment_id,
                    "mode": mode,
                    "config_hash": config_hash,
                    "delay_setting": delay_setting,
                    "method": method,
                    "t": int(t),
                    "mean_cumulative_Rc": mean,
                    "se_cumulative_Rc": se,
                    "ci95_low": mean - 1.96 * se,
                    "ci95_high": mean + 1.96 * se,
                }
            )
        pd.DataFrame(trajectory_rows).to_csv(summary_dir / "toy_trajectory_summary.csv", index=False)

    trajectory_path = summary_dir / "toy_trajectory_summary.csv"
    if not trajectory_path.exists() or trajectory_path.stat().st_size == 0:
        raise FileNotFoundError(f"Missing trajectory summary: {trajectory_path}")
    generate_figures(root)
    print(f"Regenerated summaries and figures for mode={args.mode}: {root}")


if __name__ == "__main__":
    main()

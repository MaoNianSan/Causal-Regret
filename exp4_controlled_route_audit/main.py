"""Canonical CLI for Exp4. Full execution never performs paper promotion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import config
import code_check
import make_tables
import plot_results
import self_check
from io_utils import create_run_context, write_output_manifest
from run_experiment4 import run_experiment4
import write_run_summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description=config.EXPERIMENT_DISPLAY_NAME
    )
    parser.add_argument("mode", choices=["fast", "full"])
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=None,
        help="Reserved execution setting recorded for reproducibility; current v1 runner is deterministic and sequential.",
    )
    arguments = parser.parse_args()
    run_context = create_run_context(arguments.mode)
    print("EXP4 CONTROLLED ROUTE AUDIT")
    print(f"Run ID: {run_context.run_id}")
    print(f"Run tier: {run_context.run_tier}")
    print(f"Output: {run_context.run_dir}")
    static = code_check.run(config.BASE_DIR)
    if static["status"] != "PASS":
        raise SystemExit("Static code contract failed before execution.")
    run_experiment4(run_context)
    print("[5/6] Generate paper-facing figures and tables")
    plot_results.run(run_context.run_dir)
    make_tables.run(run_context.run_dir)
    code_check.run(config.BASE_DIR, run_context.run_dir)
    print("[6/6] Run engineering and scientific checks")
    engineering, scientific = self_check.run(run_context.run_dir)
    write_run_summary.run(run_context.run_dir)
    write_output_manifest(run_context.run_dir)
    status = {
        "run_id": run_context.run_id,
        "engineering_status": engineering["status"],
        "scientific_status": scientific["status"],
        "paper_promotion": "NOT_RUN",
        "paper_result": False,
        "run_dir": str(run_context.run_dir),
    }
    print(json.dumps(status, indent=2))
    if engineering["status"] != "PASS" or scientific["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

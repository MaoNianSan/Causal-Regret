"""One-command Exp4 pipeline.  Every invocation creates an isolated run directory."""

from __future__ import annotations

import os

for _thread_env in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_thread_env] = "1"

import argparse
import json
from pathlib import Path

import pandas as pd

from aggregate_results import run as aggregate
from code_check import run as code_check
from make_tables import run as make_tables
from plot_results import run as plot
from run_experiment4 import run as run_experiment
from self_check import run as self_check
from write_audit_report import run as write_audit_report
from write_output_manifest import run as write_manifest


def _mark_paper_result(run_dir: Path) -> None:
    """Set the paper gate only after all semantic and static checks have passed."""
    config_path = run_dir / "logs" / "run_config.json"
    run_config = json.loads(config_path.read_text(encoding="utf-8"))
    run_config["paper_result"] = True
    config_path.write_text(json.dumps(run_config, indent=2), encoding="utf-8")
    for metadata_path in (run_dir / "figures" / "metadata").glob("*.json"):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["paper_result"] = True
        metadata["figure_status"] = "paper_eligible_full"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    for data_path in (run_dir / "figures" / "data").glob("*_data.csv"):
        data = pd.read_csv(data_path)
        data["paper_result"] = True
        data.to_csv(data_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["fast", "full"], default="fast")
    parser.add_argument("--n-jobs", type=int, default=None)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    run_dir = run_experiment(args.mode, args.n_jobs, args.run_id)
    aggregate(run_dir)
    plot(run_dir)
    make_tables(run_dir)
    passed = self_check(run_dir) and code_check(run_dir)
    write_audit_report(run_dir)
    if passed and args.mode == "full":
        _mark_paper_result(run_dir)
    write_manifest(run_dir)
    print(f"RUN_DIR={run_dir}")
    print(f"PIPELINE={'PASSED' if passed else 'FAILED'}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

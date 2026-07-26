"""Independent paper-promotion command for a completed full Exp4 run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import config
import make_tables
import plot_results
from io_utils import write_json, write_output_manifest, write_parquet


def _update_csv_paper_status(path: Path) -> None:
    frame = pd.read_csv(path)
    if "paper_result" in frame.columns:
        frame["paper_result"] = True
        frame.to_csv(path, index=False)


def _update_parquet_paper_status(path: Path) -> None:
    frame = pd.read_parquet(path)
    if "paper_result" in frame.columns:
        frame["paper_result"] = True
        write_parquet(frame, path)


def validate_paper_promotion(run_dir: Path, approve_claims: bool) -> dict[str, object]:
    run_config_path = run_dir / "logs" / "run_config.json"
    run_config = json.loads(run_config_path.read_text(encoding="utf-8"))
    engineering = json.loads(
        (run_dir / "checks" / "exp4_self_check.json").read_text(encoding="utf-8")
    )
    scientific = json.loads(
        (run_dir / "checks" / "exp4_scientific_check.json").read_text(encoding="utf-8")
    )
    required = [run_dir / "derived" / name for name in config.REQUIRED_DERIVED_FILES]
    figures = [
        run_dir / "figures" / "pdf" / f"{stem}.pdf"
        for stem in config.PRIMARY_FIGURE_STEMS
    ]
    tables = [run_dir / "tables" / "tbl_exp4_audit_reliability.tex"]
    checks = {
        "run_tier_is_full": run_config["run_tier"] == "full",
        "engineering_status_pass": engineering["status"] == "PASS",
        "scientific_status_pass": scientific["status"] == "PASS",
        "all_primary_full_runs_complete": all(path.exists() for path in required),
        "all_main_figures_reconstructable": all(path.exists() for path in figures),
        "all_main_tables_reconstructable": all(path.exists() for path in tables),
        "paper_claims_within_scope": bool(approve_claims),
        "result_schema_current": run_config["result_schema"] == config.RESULT_SCHEMA,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {"status": status, "checks": checks}


def promote(run_dir: Path, approve_claims: bool) -> None:
    promotion = validate_paper_promotion(run_dir, approve_claims)
    write_json(promotion, run_dir / "checks" / "exp4_promotion_check.json")
    if promotion["status"] != "PASS":
        raise SystemExit("Paper promotion failed. Inspect exp4_promotion_check.json.")
    run_config_path = run_dir / "logs" / "run_config.json"
    run_config = json.loads(run_config_path.read_text(encoding="utf-8"))
    run_config["paper_result"] = True
    run_config["is_paper_eligible"] = True
    write_json(run_config, run_config_path)
    status_path = run_dir / "logs" / "exp4_result_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["paper_result"] = True
    status["paper_promotion"] = "PASS"
    write_json(status, status_path)
    for path in sorted((run_dir / "derived").glob("*.csv")):
        _update_csv_paper_status(path)
    for path in sorted((run_dir / "derived").glob("*.parquet")):
        _update_parquet_paper_status(path)
    plot_results.run(run_dir)
    make_tables.run(run_dir)
    write_output_manifest(run_dir)
    print(f"Paper promotion PASS: {run_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--approve-claims",
        action="store_true",
        help="Explicitly confirm that manuscript claims remain within the frozen design scope.",
    )
    arguments = parser.parse_args()
    promote(arguments.run_dir, arguments.approve_claims)

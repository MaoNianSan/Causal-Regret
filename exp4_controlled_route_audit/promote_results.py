"""Independent paper-promotion command for an approved full Exp4 v2 run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from exp4.configuration.schema import MAIN_FIGURE_ID, MAIN_TABLE_ID, REQUIRED_DERIVED_FILES, RESULT_SCHEMA
from exp4.outputs.manifests import write_output_manifest
from exp4.outputs.writers import write_json


def validate_paper_promotion(run_dir: Path, approve_claims: bool) -> dict[str, object]:
    run_config = json.loads((run_dir / "logs" / "run_config.json").read_text(encoding="utf-8"))
    engineering = json.loads((run_dir / "checks" / "exp4_engineering_checks.json").read_text(encoding="utf-8"))
    scientific = json.loads((run_dir / "checks" / "exp4_scientific_checks.json").read_text(encoding="utf-8"))
    checks = {
        "run_tier_is_full": run_config["run_tier"] == "full",
        "result_schema_is_v2": run_config["result_schema"] == RESULT_SCHEMA,
        "engineering_status_pass": engineering["status"] == "PASS",
        "scientific_status_pass": scientific["status"] == "PASS",
        "all_required_derived_files_complete": all((run_dir / path).exists() for path in REQUIRED_DERIVED_FILES),
        "main_figure_complete": (run_dir / "figures" / "pdf" / f"{MAIN_FIGURE_ID}.pdf").exists(),
        "main_table_complete": (run_dir / "tables" / f"{MAIN_TABLE_ID}.tex").exists(),
        "paper_claims_within_scope": bool(approve_claims),
        "monte_carlo_precision_pass": any(
            row["check_name"] == "MONTE_CARLO_PRECISION" and row["status"] == "PASS"
            for row in scientific["checks"]
        ),
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


def promote(run_dir: Path, approve_claims: bool) -> None:
    result = validate_paper_promotion(run_dir, approve_claims)
    write_json(result, run_dir / "checks" / "exp4_promotion_check.json")
    if result["status"] != "PASS":
        raise SystemExit("Exp4 v2 paper promotion refused; inspect exp4_promotion_check.json")
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
    write_output_manifest(run_dir)
    print(f"Paper promotion PASS: {run_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--approve-claims", action="store_true")
    arguments = parser.parse_args()
    promote(arguments.run_dir, arguments.approve_claims)

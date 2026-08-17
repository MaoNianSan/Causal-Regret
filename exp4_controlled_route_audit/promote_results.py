"""Independent paper-promotion command for an approved full Exp4 v3 run.

Promotion validation does not trust the previously written check files alone:
it re-derives the main-table semantics, the Monte Carlo precision gates, and
the simulation provenance from the run artifacts and the current source tree.
``--dry-run`` writes only ``checks/exp4_promotion_check.json`` and never
modifies ``run_config.json``, ``exp4_result_status.json``, or the output
manifest.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from exp4.configuration.schema import (
    MAIN_FIGURE_ID,
    MAIN_TABLE_ID,
    REQUIRED_DERIVED_FILES,
    RESULT_SCHEMA,
)
from exp4.outputs.manifests import write_output_manifest
from exp4.outputs.writers import (
    SOURCE_HASH_ALGORITHM_VERSION,
    write_json,
)
from exp4.validation.precision_checks import promotion_precision_checks
from exp4.validation.run_provenance import audit_run_provenance
from exp4.validation.table_checks import validate_main_calibration_table


def validate_paper_promotion(
    run_dir: Path, approve_claims: bool, base_dir: Path, dry_run: bool = True
) -> dict[str, object]:
    run_config = json.loads(
        (run_dir / "logs" / "run_config.json").read_text(encoding="utf-8")
    )
    engineering = json.loads(
        (run_dir / "checks" / "exp4_engineering_checks.json").read_text(
            encoding="utf-8"
        )
    )
    scientific = json.loads(
        (run_dir / "checks" / "exp4_scientific_checks.json").read_text(encoding="utf-8")
    )
    contrasts = pd.read_csv(
        run_dir / "derived" / "module_a" / "exp4_module_a_paired_contrasts.csv"
    )
    control_summary = pd.read_csv(
        run_dir / "derived" / "module_c" / "exp4_module_c_control_summary.csv"
    )
    table_result = validate_main_calibration_table(
        control_summary,
        run_dir / "tables" / f"{MAIN_TABLE_ID}.csv",
        run_dir / "tables" / f"{MAIN_TABLE_ID}.tex",
    )
    precision = promotion_precision_checks(run_config, contrasts)
    provenance = audit_run_provenance(run_dir, base_dir)
    stages = provenance["stages"]
    checks = {
        "run_tier_is_full": run_config["run_tier"] == "full",
        "result_schema_is_v3": run_config["result_schema"] == RESULT_SCHEMA,
        "engineering_status_pass": engineering["status"] == "PASS",
        "scientific_status_pass": scientific["status"] == "PASS",
        "all_required_derived_files_complete": all(
            (run_dir / path).exists() for path in REQUIRED_DERIVED_FILES
        ),
        "main_figure_complete": (
            run_dir / "figures" / "pdf" / f"{MAIN_FIGURE_ID}.pdf"
        ).exists(),
        "main_table_exists": table_result.checks.get("main_table_csv_exists", False)
        and table_result.checks.get("main_table_tex_exists", False),
        "main_table_has_required_rows": table_result.checks.get(
            "main_table_has_exactly_two_rows", False
        ),
        "main_table_values_finite": table_result.checks.get(
            "main_table_values_finite", False
        ),
        "main_table_matches_source": table_result.checks.get(
            "main_table_matches_source", False
        ),
        "main_table_latex_nonempty": table_result.checks.get(
            "main_table_latex_has_two_data_rows", False
        )
        and table_result.checks.get("main_table_latex_has_data_beyond_rules", False),
        "main_table_complete": table_result.passed,
        "paper_claims_within_scope": bool(approve_claims),
        "primary_contrast_contract_valid": precision["primary_contrast_contract_valid"],
        "primary_monte_carlo_precision_pass": precision[
            "primary_monte_carlo_precision_pass"
        ],
        "no_nonfull_precision_status_in_full_run": precision[
            "no_nonfull_precision_status_in_full_run"
        ],
        "monte_carlo_precision_pass": all(
            precision[key]
            for key in (
                "primary_contrast_contract_valid",
                "primary_monte_carlo_precision_pass",
                "no_nonfull_precision_status_in_full_run",
            )
        ),
        # --- Run lineage contract ---
        "run_lineage_present": bool(provenance["run_lineage_present"]),
        "run_lineage_valid": bool(provenance["run_lineage_valid"]),
        "formal_full_started_clean": bool(provenance["formal_full_started_clean"]),
        # --- Stage provenance records and stored-vs-current hash comparisons ---
        "simulation_stage_record_present": bool(stages["simulation"]["record_present"]),
        "aggregation_stage_record_present": bool(
            stages["aggregation"]["record_present"]
        ),
        "reporting_stage_record_present": bool(stages["reporting"]["record_present"]),
        "validation_stage_record_present": bool(stages["validation"]["record_present"]),
        "simulation_stage_hash_match": bool(stages["simulation"]["hash_match"]),
        "aggregation_stage_hash_match": bool(stages["aggregation"]["hash_match"]),
        "reporting_stage_hash_match": bool(stages["reporting"]["hash_match"]),
        "validation_stage_hash_match": bool(stages["validation"]["hash_match"]),
        "simulation_provenance_verified": bool(
            provenance["simulation_provenance_verified"]
        ),
        "downstream_provenance_verified": bool(
            provenance["downstream_provenance_verified"]
        ),
        "reporting_provenance_verified": bool(
            provenance["reporting_provenance_verified"]
        ),
        "source_hash_algorithm_version_present": bool(
            provenance["source_hash_algorithm_version_present"]
        )
        and provenance["expected_source_hash_algorithm_version"]
        == SOURCE_HASH_ALGORITHM_VERSION,
    }
    # Mode-specific requirements: full-tree and commit equality are historical
    # metadata, not reuse gates. A FRESH run proves its own simulation stage;
    # a REUSED run additionally proves the source run and reconciliation.
    if provenance["simulation_execution_mode"] == "FRESH":
        checks.update(
            {
                "fresh_simulation_source_run_id_absent": provenance[
                    "simulation_source_run_id"
                ]
                is None,
                "fresh_recorded_commit_matches_run_config": provenance[
                    "stored_git_head_commit"
                ]
                == str(run_config.get("code_commit", "")),
                "fresh_simulation_stage_verified": bool(
                    provenance["simulation_provenance_verified"]
                ),
                "fresh_config_hash_match": bool(provenance["config_hash_match"]),
                "fresh_calibration_hash_consistent": bool(
                    provenance["calibration_hash_consistent"]
                ),
            }
        )
    elif provenance["simulation_execution_mode"] == "REUSED":
        checks.update(
            {
                "reused_source_run_id_present": bool(
                    provenance["simulation_source_run_id"]
                ),
                "reused_reconciliation_artifact_present": bool(
                    provenance["reconciliation_artifact_present"]
                ),
                "reused_current_downstream_hashes_match": all(
                    bool(stages[name]["hash_match"])
                    for name in ("aggregation", "reporting", "validation")
                ),
            }
        )
    else:
        checks["simulation_execution_mode_known"] = False
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "provenance": {
            key: provenance[key]
            for key in (
                "stored_source_code_hash",
                "current_pre_fix_source_code_hash",
                "source_hash_match",
                "config_hash_match",
                "full_simulation_reuse_decision",
                "full_simulation_reuse_eligibility",
                "simulation_execution_mode",
                "simulation_source_run_id",
                "downstream_execution_mode",
                "downstream_source_run_id",
                "run_lineage_present",
                "run_lineage_valid",
                "formal_full_started_clean",
                "source_unchanged_during_run",
                "simulation_provenance_verified",
                "downstream_provenance_verified",
                "source_hash_algorithm_version_present",
                "stage_source_hashes",
                "stages",
            )
        },
        "table": table_result.as_dict(),
        "precision": precision,
    }


def promote(run_dir: Path, approve_claims: bool, base_dir: Path, dry_run: bool) -> None:
    result = validate_paper_promotion(
        run_dir, approve_claims, base_dir, dry_run=dry_run
    )
    write_json(result, run_dir / "checks" / "exp4_promotion_check.json")
    if result["status"] != "PASS":
        raise SystemExit(
            "Exp4 v3 paper promotion refused; inspect exp4_promotion_check.json"
        )
    if dry_run:
        print(f"Paper promotion dry-run PASS (no state written): {run_dir}")
        return
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
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    base_dir = Path(__file__).resolve().parent
    promote(
        arguments.run_dir, arguments.approve_claims, base_dir, dry_run=arguments.dry_run
    )

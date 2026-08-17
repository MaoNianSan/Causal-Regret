"""Write engineering and scientific validation payloads for a completed run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from exp4.configuration.schema import (
    APPENDIX_FIGURE_IDS,
    MAIN_FIGURE_ID,
    MAIN_TABLE_ID,
    REQUIRED_DERIVED_FILES,
    RESULT_SCHEMA,
)
from exp4.outputs.writers import write_json
from exp4.validation.boundary_checks import exp1_exp4_boundary_check
from exp4.validation.invariants import scientific_checks
from exp4.validation.precision_checks import validate_monte_carlo_precision, write_precision_checks
from exp4.validation.provenance_checks import (
    figure_sources_reconstructable,
    manifest_paths_are_relative_and_exist,
)
from exp4.validation.schema_checks import (
    MODULE_A_COLUMNS,
    MODULE_B_CONDITION_COLUMNS,
    MODULE_B_UNIT_COLUMNS,
    MODULE_C_COLUMNS,
    has_columns,
)
from exp4.validation.table_checks import (
    validate_and_write_table_checks,
    ValidationResult,
)


def _row(name: str, passed: bool, details: str) -> dict[str, str]:
    return {"check_name": name, "status": "PASS" if passed else "FAIL", "details": details}


def validate_run(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    run_config = json.loads((run_dir / "logs" / "run_config.json").read_text(encoding="utf-8"))
    seed_level = pd.read_parquet(run_dir / "derived" / "module_a" / "exp4_module_a_seed_level.parquet")
    unit_level = pd.read_parquet(run_dir / "derived" / "module_b" / "exp4_module_b_audit_unit_level.parquet")
    condition_level = pd.read_parquet(run_dir / "derived" / "module_b" / "exp4_module_b_condition_level.parquet")
    c_replication = pd.read_parquet(run_dir / "derived" / "module_c" / "exp4_module_c_replication_level.parquet")
    required = [run_dir / relative for relative in REQUIRED_DERIVED_FILES]
    figure_ids = (MAIN_FIGURE_ID,) + APPENDIX_FIGURE_IDS
    figure_complete = all(
        (run_dir / "figures" / extension / f"{figure_id}.{extension if extension != 'png' else 'png'}").exists()
        for figure_id in figure_ids
        for extension in ("pdf", "png")
    )
    # The comprehension above intentionally checks pdf/pdf and png/png directory/file pairs.
    figure_complete = all(
        (run_dir / "figures" / "pdf" / f"{figure_id}.pdf").exists()
        and (run_dir / "figures" / "png" / f"{figure_id}.png").exists()
        and (run_dir / "figures" / "data" / f"{figure_id}_data.csv").exists()
        and (run_dir / "figures" / "metadata" / f"{figure_id}_metadata.json").exists()
        for figure_id in figure_ids
    )
    sources_ok, sources_details = figure_sources_reconstructable(run_dir, figure_ids)
    paths_ok, paths_details = manifest_paths_are_relative_and_exist(
        run_dir,
        [
            run_dir / "logs" / "exp4_module_a_path_manifest.csv",
            run_dir / "logs" / "exp4_module_bc_path_manifest.csv",
        ],
    )
    boundary_ok, boundary_details = exp1_exp4_boundary_check(
        run_dir, MAIN_FIGURE_ID, MAIN_TABLE_ID
    )
    schema_checks = (
        ("module_a_schema", *has_columns(seed_level, MODULE_A_COLUMNS)),
        ("module_b_unit_schema", *has_columns(unit_level, MODULE_B_UNIT_COLUMNS)),
        ("module_b_condition_schema", *has_columns(condition_level, MODULE_B_CONDITION_COLUMNS)),
        ("module_c_schema", *has_columns(c_replication, MODULE_C_COLUMNS)),
    )
    control_summary = pd.read_csv(run_dir / "derived" / "module_c" / "exp4_module_c_control_summary.csv")
    table_result: ValidationResult = validate_and_write_table_checks(run_dir, control_summary)
    contrasts = pd.read_csv(run_dir / "derived" / "module_a" / "exp4_module_a_paired_contrasts.csv")
    precision_result = validate_monte_carlo_precision(contrasts, str(run_config["run_tier"]))
    write_precision_checks(run_dir, precision_result)
    engineering_rows = [
        _row("required_derived_files_complete", all(path.exists() for path in required), f"missing={[path.relative_to(run_dir).as_posix() for path in required if not path.exists()]}"),
        _row("result_schema_is_v3", run_config["result_schema"] == RESULT_SCHEMA and set(seed_level["result_schema"]) == {RESULT_SCHEMA}, f"run_schema={run_config['result_schema']}"),
        _row("run_remains_nonpaper", run_config["paper_result"] is False and bool(seed_level["paper_result"].eq(False).all()), f"paper_result={run_config['paper_result']}"),
        _row("figure_bundles_complete", figure_complete, f"figure_count={len(figure_ids)}"),
        _row("figure_sources_reconstructable", sources_ok, sources_details),
        _row("path_manifests_portable", paths_ok, paths_details),
        _row("main_table_exists", bool(table_result.checks.get("main_table_csv_exists", False) and table_result.checks.get("main_table_tex_exists", False)), MAIN_TABLE_ID),
        _row("main_table_has_required_rows", bool(table_result.checks.get("main_table_has_exactly_two_rows", False)), f"rows={table_result.details.get('main_table_row_count')}"),
        _row("main_table_values_finite", bool(table_result.checks.get("main_table_values_finite", False)), f"has_nan={table_result.details.get('main_table_has_nan')}"),
        _row("main_table_matches_source", bool(table_result.checks.get("main_table_matches_source", False)), f"mismatches={table_result.details.get('value_mismatches')}"),
        _row("main_table_latex_nonempty", bool(table_result.checks.get("main_table_latex_has_two_data_rows", False)) and bool(table_result.checks.get("main_table_latex_has_data_beyond_rules", False)), f"data_rows={table_result.details.get('main_table_latex_data_row_count')}"),
        _row("main_table_complete", table_result.passed, f"semantic_checks={sum(table_result.checks.values())}/{len(table_result.checks)}"),
        _row("primary_contrast_contract_valid", bool(precision_result.checks.get("primary_contrast_contract_valid", False)), f"count={precision_result.primary_contrast_count}"),
        _row("primary_monte_carlo_precision_pass", precision_result.engineering_pass(), precision_result.details),
        _row("no_nonfull_precision_status_in_full_run", bool(precision_result.checks.get("no_nonfull_precision_status_in_full_run", False)), f"run_tier={precision_result.run_tier}"),
    ]
    engineering_rows.extend(_row(name, passed, details) for name, passed, details in schema_checks)
    scientific_rows = [_row(name, passed, details) for name, passed, details in scientific_checks(run_dir)]
    scientific_rows.append(_row("FIGURE_SOURCE_RECONSTRUCTABLE", sources_ok, sources_details))
    scientific_rows.append(_row("EXP1_EXP4_BOUNDARY", boundary_ok, boundary_details))
    engineering = {
        "check_type": "engineering",
        "status": "PASS" if all(row["status"] == "PASS" for row in engineering_rows) else "FAIL",
        "checks": engineering_rows,
    }
    scientific = {
        "check_type": "scientific",
        "status": "PASS" if all(row["status"] == "PASS" for row in scientific_rows) else "FAIL",
        "checks": scientific_rows,
    }
    write_json(engineering, run_dir / "checks" / "exp4_engineering_checks.json")
    write_json(scientific, run_dir / "checks" / "exp4_scientific_checks.json")
    return engineering, scientific

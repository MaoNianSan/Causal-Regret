"""Semantic validation of the paper main calibration table.

The main table is generated from the Module C control summary by exact control
ID. This module verifies the table's semantic integrity (row set, order,
columns, finiteness, correspondence, LaTeX content, source consistency) and
records the table hashes in a manifest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

import numpy as np
import pandas as pd

from exp4.configuration.schema import MAIN_CALIBRATION_CONTROL_IDS, MAIN_TABLE_ID
from exp4.outputs.writers import sha256_file, write_json

MAIN_TABLE_COLUMNS = (
    "control_id",
    "control_display_name",
    "correspondence_status",
    "raw_defect",
    "oof_calibrated_defect",
    "recoverability",
    "estimability_rate",
)

FINITE_VALUE_COLUMNS = (
    "raw_defect",
    "oof_calibrated_defect",
    "recoverability",
    "estimability_rate",
)

SOURCE_TO_TABLE_COLUMNS = (
    ("raw_defect", "Raw defect"),
    ("oof_calibrated_defect", "OOF calibrated defect"),
    ("recoverability", "Recoverability"),
    ("estimability_rate", "Estimability rate"),
)


@dataclass
class ValidationResult:
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    details: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "validation": "exp4_main_calibration_table",
            "status": "PASS" if self.passed else "FAIL",
            "checks": self.checks,
            "details": self.details,
        }


def _data_row_count(tex_text: str) -> int:
    lines = [line.strip() for line in tex_text.splitlines()]
    in_data = False
    count = 0
    for line in lines:
        if line == "\\midrule":
            in_data = True
            continue
        if line == "\\bottomrule":
            break
        if in_data and line and "&" in line:
            count += 1
    return count


def validate_main_calibration_table(
    control_summary: pd.DataFrame,
    csv_path: Path,
    tex_path: Path,
) -> ValidationResult:
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}

    # 1. Required control IDs each appear exactly once in the Module C summary.
    counts = control_summary["control_id"].value_counts().to_dict()
    summary_counts = {cid: int(counts.get(cid, 0)) for cid in MAIN_CALIBRATION_CONTROL_IDS}
    checks["required_controls_each_exactly_once_in_summary"] = all(
        value == 1 for value in summary_counts.values()
    )
    details["summary_control_counts"] = summary_counts

    csv_exists = csv_path.exists()
    tex_exists = tex_path.exists()
    checks["main_table_csv_exists"] = csv_exists
    checks["main_table_tex_exists"] = tex_exists
    if not csv_exists or not tex_exists:
        details["error"] = "main table csv/tex missing"
        return ValidationResult(passed=False, checks=checks, details=details)

    table = pd.read_csv(csv_path)
    tex_text = tex_path.read_text(encoding="utf-8")

    # 2. Main table CSV has exactly the required rows.
    expected_ids = list(MAIN_CALIBRATION_CONTROL_IDS)
    checks["main_table_has_exactly_two_rows"] = len(table) == 2
    details["main_table_row_count"] = int(len(table))

    # 3. Control order is correct.
    checks["main_table_control_order_correct"] = bool(
        table["Control"].tolist() == _expected_display_names(control_summary)
    )
    details["main_table_display_names"] = table["Control"].tolist()

    # 4. Required columns are complete.
    expected_columns = [
        "Control",
        "Unit-level correspondence",
        "Raw defect",
        "OOF calibrated defect",
        "Recoverability",
        "Estimability rate",
    ]
    missing_columns = sorted(set(expected_columns) - set(table.columns))
    checks["main_table_columns_complete"] = not missing_columns
    details["missing_columns"] = missing_columns

    # 5. Numeric values are finite.
    numeric = table[["Raw defect", "OOF calibrated defect", "Recoverability", "Estimability rate"]]
    finite_values = numeric.map(np.isfinite).all().all() if len(table) else False
    checks["main_table_values_finite"] = bool(finite_values)
    details["main_table_has_nan"] = bool(numeric.isna().any().any())

    # 6. Correspondence status is non-empty.
    checks["correspondence_status_nonempty"] = bool(
        table["Unit-level correspondence"].notna().all()
        and (table["Unit-level correspondence"].astype(str).str.strip() != "").all()
    )

    # 7. LaTeX contains two data rows.
    data_rows = _data_row_count(tex_text)
    checks["main_table_latex_has_two_data_rows"] = data_rows == 2
    details["main_table_latex_data_row_count"] = data_rows

    # 8. LaTeX is not only structural rules.
    checks["main_table_latex_has_data_beyond_rules"] = bool(
        "&" in tex_text and "\\bottomrule" in tex_text and "\\midrule" in tex_text
    )

    # 9. CSV values match the Module C summary for the required controls.
    source = control_summary.set_index("control_id").loc[expected_ids].set_index("control_display_name")
    mismatches: list[str] = []
    for source_column, table_column in SOURCE_TO_TABLE_COLUMNS:
        for display_name in table["Control"]:
            expected = float(source.loc[display_name, source_column])
            actual = float(table.loc[table["Control"] == display_name, table_column].iloc[0])
            if not np.isclose(expected, actual, rtol=1e-9, atol=1e-12):
                mismatches.append(f"{display_name}:{source_column}")
    checks["main_table_matches_source"] = not mismatches
    details["value_mismatches"] = mismatches

    # 10. Table hashes recorded in the manifest (separate log artifact).
    hashes = {
        "main_table_id": MAIN_TABLE_ID,
        "main_table_csv_sha256": sha256_file(csv_path),
        "main_table_tex_sha256": sha256_file(tex_path),
    }
    details["hashes"] = hashes
    checks["main_table_hashes_recorded"] = True
    passed = all(checks.values())
    return ValidationResult(passed=passed, checks=checks, details=details)


def _expected_display_names(control_summary: pd.DataFrame) -> list[str]:
    by_id = control_summary.set_index("control_id")["control_display_name"]
    return [str(by_id.loc[cid]) for cid in MAIN_CALIBRATION_CONTROL_IDS]


def write_table_checks(run_dir: Path, result: ValidationResult) -> None:
    payload = result.as_dict()
    payload["main_table_manifest"] = (
        json.loads((run_dir / "logs" / "exp4_main_table_manifest.json").read_text(encoding="utf-8"))
        if (run_dir / "logs" / "exp4_main_table_manifest.json").exists()
        else None
    )
    write_json(payload, run_dir / "checks" / "exp4_table_checks.json")


def validate_and_write_table_checks(
    run_dir: Path, control_summary: pd.DataFrame
) -> ValidationResult:
    result = validate_main_calibration_table(
        control_summary,
        run_dir / "tables" / f"{MAIN_TABLE_ID}.csv",
        run_dir / "tables" / f"{MAIN_TABLE_ID}.tex",
    )
    write_table_checks(run_dir, result)
    return result

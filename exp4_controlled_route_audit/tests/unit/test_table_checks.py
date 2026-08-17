"""Tests for the semantic main-table validation and the control-tier fix."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from exp4.configuration.schema import MAIN_CALIBRATION_CONTROL_IDS, MAIN_TABLE_ID
from exp4.reporting.aggregate_module_c import aggregate_control_summary
from exp4.reporting.tables import _write_table, select_main_calibration_rows
from exp4.validation.table_checks import (
    validate_main_calibration_table,
    validate_and_write_table_checks,
)


def _control_summary() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "control_id": ["affine_linked", "blocked_correspondence_destroyed", "nonlinear_monotone"],
            "control_display_name": [
                "Affine-linked control",
                "Temporally blocked correspondence-destroyed control",
                "Nonlinear monotone control",
            ],
            "analysis_tier": ["primary", "primary", "appendix"],
            "correspondence_status": [
                "preserved by construction",
                "destroyed within temporal blocks",
                "monotone but outside affine family",
            ],
            "raw_pairwise_discrepancy": [0.59, 1.44, 0.19],
            "oof_calibrated_pairwise_discrepancy": [0.16, 0.88, 0.11],
            "recoverability": [0.74, 0.39, 0.41],
            "estimability_rate": [1.0, 1.0, 1.0],
        }
    )


def _write_fixture(run_dir: Path, summary: pd.DataFrame) -> tuple[Path, Path]:
    (run_dir / "tables").mkdir(parents=True, exist_ok=True)
    main = select_main_calibration_rows(summary)
    _write_table(
        main,
        run_dir / "tables" / MAIN_TABLE_ID,
        "Calibration-family controls and correspondence status.",
        "tab:exp4_calibration_controls",
    )
    return run_dir / "tables" / f"{MAIN_TABLE_ID}.csv", run_dir / "tables" / f"{MAIN_TABLE_ID}.tex"


def test_main_calibration_table_has_exact_primary_controls(tmp_path: Path) -> None:
    csv_path, _ = _write_fixture(tmp_path, _control_summary())
    table = pd.read_csv(csv_path)
    assert set(table["Control"]) == {
        "Affine-linked control",
        "Temporally blocked correspondence-destroyed control",
    }
    assert "Nonlinear monotone control" not in set(table["Control"])


def test_main_calibration_table_has_two_rows(tmp_path: Path) -> None:
    csv_path, _ = _write_fixture(tmp_path, _control_summary())
    assert len(pd.read_csv(csv_path)) == 2


def test_main_calibration_table_rejects_mixed_or_empty_selection(tmp_path: Path) -> None:
    # Old logic filtered analysis_tier == "primary" and produced an empty table
    # when every summary row carried analysis_tier == "mixed". The new selection
    # is by exact control ID, so a mixed-tier summary must still yield the two
    # primary controls.
    summary = _control_summary().copy()
    summary["analysis_tier"] = "mixed"
    csv_path, _ = _write_fixture(tmp_path, summary)
    table = pd.read_csv(csv_path)
    assert len(table) == 2
    # A summary missing a required control ID must be rejected, not silently
    # produce a partial/empty table.
    broken = _control_summary().drop(_control_summary().index[1])
    with pytest.raises(ValueError):
        select_main_calibration_rows(broken)


def test_main_calibration_table_numeric_values_are_finite(tmp_path: Path) -> None:
    csv_path, _ = _write_fixture(tmp_path, _control_summary())
    result = validate_main_calibration_table(
        _control_summary(), csv_path, csv_path.with_suffix(".tex")
    )
    assert result.checks["main_table_values_finite"] is True


def test_main_calibration_latex_contains_two_data_rows(tmp_path: Path) -> None:
    csv_path, tex_path = _write_fixture(tmp_path, _control_summary())
    text = tex_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    in_data = False
    data_rows = 0
    for line in lines:
        stripped = line.strip()
        if stripped == "\\midrule":
            in_data = True
            continue
        if stripped == "\\bottomrule":
            break
        if in_data and "&" in stripped:
            data_rows += 1
    assert data_rows == 2
    result = validate_main_calibration_table(_control_summary(), csv_path, tex_path)
    assert result.checks["main_table_latex_has_two_data_rows"] is True


def test_promotion_rejects_empty_main_table(tmp_path: Path) -> None:
    # A LaTeX file that exists but has no data rows must fail validation.
    csv_path, tex_path = _write_fixture(tmp_path, _control_summary())
    tex_path.write_text(
        "\\begin{table}[t]\n\\toprule\n\\midrule\n\\bottomrule\n\\end{table}\n",
        encoding="utf-8",
    )
    result = validate_main_calibration_table(_control_summary(), csv_path, tex_path)
    assert result.passed is False
    assert result.checks["main_table_latex_has_two_data_rows"] is False


def test_table_matches_module_c_summary(tmp_path: Path) -> None:
    csv_path, tex_path = _write_fixture(tmp_path, _control_summary())
    result = validate_main_calibration_table(_control_summary(), csv_path, tex_path)
    assert result.checks["main_table_matches_source"] is True
    assert result.checks["main_table_control_order_correct"] is True


def test_validate_and_write_table_checks_writes_json(tmp_path: Path) -> None:
    _write_fixture(tmp_path, _control_summary())
    result = validate_and_write_table_checks(tmp_path, _control_summary())
    assert result.passed is True
    payload = json.loads((tmp_path / "checks" / "exp4_table_checks.json").read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert "hashes" in payload["details"]


def test_aggregate_control_summary_assigns_registry_tiers() -> None:
    # Replication-level rows carrying a stale/mixed tier must be repaired to the
    # frozen CONTROL_REGISTRY tiers at aggregation time.
    replication = pd.DataFrame(
        {
            "control_id": ["affine_linked", "affine_linked", "blocked_correspondence_destroyed", "nonlinear_monotone"],
            "control_display_name": [
                "Affine-linked control",
                "Affine-linked control",
                "Temporally blocked correspondence-destroyed control",
                "Nonlinear monotone control",
            ],
            "analysis_tier": ["mixed", "mixed", "mixed", "mixed"],
            "correspondence_status": ["preserved by construction", "preserved by construction", "destroyed within temporal blocks", "monotone but outside affine family"],
            "raw_pairwise_discrepancy": [0.5, 0.7, 1.4, 0.2],
            "oof_calibrated_pairwise_discrepancy": [0.1, 0.2, 0.9, 0.1],
            "recoverability": [0.8, 0.7, 0.4, 0.4],
            "negative_recoverability_indicator": [0.0, 0.0, 0.0, 0.0],
            "estimable": [True, True, True, True],
            "minimum_training_support": [100, 100, 100, 100],
            "replication_id": [1, 2, 1, 1],
        }
    )
    summary = aggregate_control_summary(replication)
    tiers = summary.set_index("control_id")["analysis_tier"].to_dict()
    assert tiers["affine_linked"] == "primary"
    assert tiers["blocked_correspondence_destroyed"] == "primary"
    assert tiers["nonlinear_monotone"] == "appendix"
    assert len(summary) == 3

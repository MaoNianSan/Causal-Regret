"""Regression tests for the post-full-fix behavior (small temporary fixtures).

These tests pin the exact release-blocking defects and their fixes without
depending on the full 1000-replication simulation outputs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from exp4.configuration.schema import MAIN_TABLE_ID
from exp4.reporting.aggregate_module_a import summarize_paired_contrasts
from exp4.reporting.tables import _write_table, select_main_calibration_rows
from exp4.validation.precision_checks import validate_monte_carlo_precision
from exp4.validation.table_checks import validate_main_calibration_table
from promote_results import validate_paper_promotion

ROOT = Path(__file__).resolve().parents[1]


def _mixed_tier_summary() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "control_id": ["affine_linked", "blocked_correspondence_destroyed", "nonlinear_monotone"],
            "control_display_name": [
                "Affine-linked control",
                "Temporally blocked correspondence-destroyed control",
                "Nonlinear monotone control",
            ],
            "analysis_tier": ["mixed", "mixed", "mixed"],
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


def test_regression_mixed_tier_summary_produces_empty_table_under_old_logic() -> None:
    # Old logic filtered analysis_tier == "primary"; with every row "mixed" the
    # main table degenerated to a header-only CSV.
    summary = _mixed_tier_summary()
    old_selection = summary[summary["analysis_tier"] == "primary"]
    assert len(old_selection) == 0


def test_regression_new_logic_generates_two_row_main_table(tmp_path: Path) -> None:
    summary = _mixed_tier_summary()
    main = select_main_calibration_rows(summary)
    assert len(main) == 2
    assert main["Control"].tolist() == [
        "Affine-linked control",
        "Temporally blocked correspondence-destroyed control",
    ]
    _write_table(main, tmp_path / MAIN_TABLE_ID, "caption", "label")
    csv_text = (tmp_path / f"{MAIN_TABLE_ID}.csv").read_text(encoding="utf-8")
    assert csv_text.count("\n") - 1 == 2  # header + 2 data rows


def test_regression_full_run_with_nonfull_precision_status_fails() -> None:
    contrasts = pd.DataFrame(
        {
            "contrast_id": ["primary", "other"],
            "is_primary_contrast": [True, False],
            "monte_carlo_precision_gate": ["NOT_APPLICABLE_NON_FULL", "REPORTED_NOT_GATED"],
        }
    )
    result = validate_monte_carlo_precision(contrasts, "full")
    assert result.status == "FAIL"
    assert result.has_nonfull_precision_status_in_full is True


def test_regression_empty_latex_table_cannot_pass_promotion(tmp_path: Path) -> None:
    # Build a run whose LaTeX main table exists but has no data rows.
    run_dir = tmp_path / "run"
    (run_dir / "logs").mkdir(parents=True)
    (run_dir / "checks").mkdir(parents=True)
    (run_dir / "derived" / "module_a").mkdir(parents=True)
    (run_dir / "derived" / "module_c").mkdir(parents=True)
    (run_dir / "tables").mkdir(parents=True)
    (run_dir / "figures" / "pdf").mkdir(parents=True)
    (run_dir / "figures" / "data").mkdir(parents=True)
    (run_dir / "figures" / "metadata").mkdir(parents=True)
    run_config = {
        "run_id": "full_reg",
        "run_tier": "full",
        "result_schema": "exp4_controlled_route_audit_v2",
        "paper_result": False,
        "source_code_hash": "0" * 64,
        "config_hash": "0" * 64,
        "code_commit": "x",
    }
    (run_dir / "logs" / "run_config.json").write_text(json.dumps(run_config), encoding="utf-8")
    for name in ("exp4_engineering_checks.json", "exp4_scientific_checks.json"):
        (run_dir / "checks" / name).write_text(
            json.dumps({"status": "PASS", "checks": []}), encoding="utf-8"
        )
    summary = _mixed_tier_summary()
    summary.to_csv(run_dir / "derived" / "module_c" / "exp4_module_c_control_summary.csv", index=False)
    contrasts = pd.DataFrame(
        {
            "contrast_id": ["primary"],
            "is_primary_contrast": [True],
            "monte_carlo_precision_gate": ["PASS"],
        }
    )
    contrasts.to_csv(run_dir / "derived" / "module_a" / "exp4_module_a_paired_contrasts.csv", index=False)
    # Valid CSV but empty LaTeX body.
    main = select_main_calibration_rows(summary)
    _write_table(main, run_dir / "tables" / MAIN_TABLE_ID, "caption", "label")
    tex_path = run_dir / "tables" / f"{MAIN_TABLE_ID}.tex"
    tex_path.write_text(
        "\\begin{table}[t]\n\\toprule\n\\midrule\n\\bottomrule\n\\end{table}\n",
        encoding="utf-8",
    )
    (run_dir / "figures" / "pdf" / "fig_exp4_route_alignment_and_audit_reliability.pdf").write_bytes(b"x")
    result = validate_paper_promotion(run_dir, approve_claims=True, base_dir=ROOT, dry_run=True)
    assert result["checks"]["main_table_latex_nonempty"] is False
    assert result["checks"]["main_table_complete"] is False
    assert result["status"] == "FAIL"

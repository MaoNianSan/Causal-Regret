"""Main and appendix tables generated from v3 derived summaries."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from exp4.configuration.parameters import parameter_payload
from exp4.configuration.schema import MAIN_CALIBRATION_CONTROL_IDS, MAIN_TABLE_ID
from exp4.outputs.writers import sha256_file, write_json

MAIN_TABLE_COLUMNS = (
    "control_display_name",
    "correspondence_status",
    "raw_pairwise_discrepancy",
    "oof_calibrated_pairwise_discrepancy",
    "recoverability",
    "estimability_rate",
)


def _format_value(value: object) -> str:
    if pd.isna(value):
        return "NA"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _write_table(frame: pd.DataFrame, stem: Path, caption: str, label: str) -> None:
    frame.to_csv(stem.with_suffix(".csv"), index=False)
    display = frame.map(_format_value)
    latex = display.to_latex(
        index=False,
        escape=False,
        caption=caption,
        label=label,
        position="t",
    )
    stem.with_suffix(".tex").write_text(latex, encoding="utf-8")


def select_main_calibration_rows(controls: pd.DataFrame) -> pd.DataFrame:
    """Select the paper main-table control rows by exact control ID.

    Order follows MAIN_CALIBRATION_CONTROL_IDS exactly; selection is by exact
    ID match, never by string matching or analysis_tier. Any row outside the
    tuple (e.g. nonlinear_monotone) is excluded from the main table.
    """
    frame = controls.set_index("control_id")
    missing = [
        control_id
        for control_id in MAIN_CALIBRATION_CONTROL_IDS
        if control_id not in frame.index
    ]
    if missing:
        raise ValueError(
            f"Missing main-table control IDs in Module C summary: {missing}"
        )
    selected = frame.loc[list(MAIN_CALIBRATION_CONTROL_IDS)].reset_index()
    return selected[list(MAIN_TABLE_COLUMNS)].rename(
        columns={
            "control_display_name": "Control",
            "correspondence_status": "Unit-level correspondence",
            "raw_pairwise_discrepancy": "Raw pairwise discrepancy",
            "oof_calibrated_pairwise_discrepancy": "OOF calibrated pairwise discrepancy",
            "recoverability": "Recoverability",
            "estimability_rate": "Estimability rate",
        }
    )


def _parameter_frame() -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for section, values in parameter_payload().items():
        for parameter, value in values.items():
            records.append({"section": section, "parameter": parameter, "value": value})
    return pd.DataFrame.from_records(records)


def _write_main_table_hashes(run_dir: Path, csv_path: Path, tex_path: Path) -> None:
    write_json(
        {
            "main_table_id": MAIN_TABLE_ID,
            "main_table_csv_sha256": sha256_file(csv_path),
            "main_table_tex_sha256": sha256_file(tex_path),
        },
        run_dir / "logs" / "exp4_main_table_manifest.json",
    )


def make_tables(run_dir: Path) -> None:
    module_a = run_dir / "derived" / "module_a"
    module_b = run_dir / "derived" / "module_b"
    module_c = run_dir / "derived" / "module_c"
    tables = run_dir / "tables"
    controls = pd.read_csv(module_c / "exp4_module_c_control_summary.csv")
    main = select_main_calibration_rows(controls)
    _write_table(
        main,
        tables / MAIN_TABLE_ID,
        "Calibration-family controls and correspondence status.",
        "tab:exp4_calibration_controls",
    )
    _write_main_table_hashes(
        run_dir, tables / f"{MAIN_TABLE_ID}.csv", tables / f"{MAIN_TABLE_ID}.tex"
    )
    appendix_sources = (
        ("tbl_app_exp4_parameters", _parameter_frame(), "Frozen Exp4 v3 parameters."),
        (
            "tbl_app_exp4_paired_contrasts",
            pd.read_csv(module_a / "exp4_module_a_paired_contrasts.csv"),
            "Shared-seed paired contrasts.",
        ),
        (
            "tbl_app_exp4_audit_performance",
            pd.read_csv(module_b / "exp4_module_b_audit_performance.csv"),
            "Audit bias, RMSE, and Monte Carlo error.",
        ),
        (
            "tbl_app_exp4_weight_diagnostics",
            pd.read_csv(module_b / "exp4_module_b_weight_diagnostics.csv"),
            "IPW support and weight diagnostics.",
        ),
        (
            "tbl_app_exp4_parameter_recovery",
            pd.read_csv(module_c / "exp4_module_c_parameter_recovery.csv"),
            "Calibration parameter recovery.",
        ),
        (
            "tbl_app_exp4_correspondence_checks",
            pd.read_csv(module_c / "exp4_module_c_correspondence_checks.csv"),
            "Blocked-permutation correspondence checks.",
        ),
    )
    for stem, frame, caption in appendix_sources:
        _write_table(frame, tables / stem, caption, f"tab:{stem}")

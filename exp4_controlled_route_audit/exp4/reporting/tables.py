"""Main and appendix tables generated from v2 derived summaries."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from exp4.configuration.parameters import parameter_payload
from exp4.configuration.schema import MAIN_TABLE_ID


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


def _parameter_frame() -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for section, values in parameter_payload().items():
        for parameter, value in values.items():
            records.append({"section": section, "parameter": parameter, "value": value})
    return pd.DataFrame.from_records(records)


def make_tables(run_dir: Path) -> None:
    module_a = run_dir / "derived" / "module_a"
    module_b = run_dir / "derived" / "module_b"
    module_c = run_dir / "derived" / "module_c"
    tables = run_dir / "tables"
    controls = pd.read_csv(module_c / "exp4_module_c_control_summary.csv")
    main = controls[controls["analysis_tier"] == "primary"][
        [
            "control_display_name",
            "correspondence_status",
            "raw_defect",
            "oof_calibrated_defect",
            "recoverability",
            "estimability_rate",
        ]
    ].rename(
        columns={
            "control_display_name": "Control",
            "correspondence_status": "Unit-level correspondence",
            "raw_defect": "Raw defect",
            "oof_calibrated_defect": "OOF calibrated defect",
            "recoverability": "Recoverability",
            "estimability_rate": "Estimability rate",
        }
    )
    _write_table(
        main,
        tables / MAIN_TABLE_ID,
        "Calibration-family controls and correspondence status.",
        "tab:exp4_calibration_controls",
    )
    appendix_sources = (
        ("tbl_app_exp4_parameters", _parameter_frame(), "Frozen Exp4 v2 parameters."),
        ("tbl_app_exp4_paired_contrasts", pd.read_csv(module_a / "exp4_module_a_paired_contrasts.csv"), "Shared-seed paired contrasts."),
        ("tbl_app_exp4_audit_performance", pd.read_csv(module_b / "exp4_module_b_audit_performance.csv"), "Audit bias, RMSE, and Monte Carlo error."),
        ("tbl_app_exp4_weight_diagnostics", pd.read_csv(module_b / "exp4_module_b_weight_diagnostics.csv"), "IPW support and weight diagnostics."),
        ("tbl_app_exp4_parameter_recovery", pd.read_csv(module_c / "exp4_module_c_parameter_recovery.csv"), "Calibration parameter recovery."),
        ("tbl_app_exp4_correspondence_checks", pd.read_csv(module_c / "exp4_module_c_correspondence_checks.csv"), "Blocked-permutation correspondence checks."),
    )
    for stem, frame, caption in appendix_sources:
        _write_table(frame, tables / stem, caption, f"tab:{stem}")

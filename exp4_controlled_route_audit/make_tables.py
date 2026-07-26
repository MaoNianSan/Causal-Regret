"""Manuscript and appendix tables from frozen derived files."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import config


def _write_latex_table(frame: pd.DataFrame, path: Path, caption: str, label: str, note: str) -> None:
    latex = frame.to_latex(
        index=False,
        escape=False,
        float_format=lambda value: "NA" if pd.isna(value) else f"{value:.3f}",
        caption=caption,
        label=label,
        position="t",
        column_format="ll" + "r" * max(0, len(frame.columns) - 2),
    )
    latex += "\n\\begin{flushleft}\n\\footnotesize\n" + note + "\n\\end{flushleft}\n"
    path.write_text(latex, encoding="utf-8")


def run(run_dir: Path) -> None:
    derived = run_dir / "derived"
    tables = run_dir / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    audit = pd.read_csv(derived / "exp4_audit_condition_summary.csv")
    boundary = pd.read_csv(derived / "exp4_route_boundary_summary.csv")
    support = pd.read_csv(derived / "exp4_effective_support_summary.csv")
    controls = pd.read_csv(derived / "exp4_calibration_control_summary.csv")
    learner = pd.read_csv(derived / "exp4_learner_consequence_appendix.csv")

    primary_audit = audit[audit["route_id"] == "proxy_label"].copy()
    primary_audit["audit_design"] = primary_audit["audit_design_id"].map(
        {key: value["display_name"] for key, value in config.AUDIT_DESIGN_REGISTRY.items()}
    )
    primary_columns = [
        "audit_evidence_rate",
        "audit_design",
        "raw_bias",
        "raw_rmse",
        "calibrated_bias",
        "calibrated_rmse",
        "recoverability_mae",
        "mean_labelled_audit_sample_size",
        "mean_effective_labelled_sample_size",
        "mean_labelled_support_coefficient",
        "calibration_estimable_rate",
    ]
    primary_table = primary_audit[primary_columns].sort_values(
        ["audit_evidence_rate", "audit_design"]
    )
    primary_table.to_csv(tables / "tbl_exp4_audit_reliability.csv", index=False)
    _write_latex_table(
        primary_table.rename(
            columns={
                "audit_evidence_rate": r"$\rho_{\mathrm{audit}}$",
                "audit_design": "Audit design",
                "raw_bias": "Raw bias",
                "raw_rmse": "Raw RMSE",
                "calibrated_bias": "Cal. bias",
                "calibrated_rmse": "Cal. RMSE",
                "recoverability_mae": "Rec. MAE",
                "mean_labelled_audit_sample_size": r"Mean $n_{\mathrm{lab}}$",
                "mean_effective_labelled_sample_size": r"Mean $n_{\mathrm{eff}}$",
                "mean_labelled_support_coefficient": r"Mean $\omega_M$",
                "calibration_estimable_rate": "Estimable",
            }
        ),
        tables / "tbl_exp4_audit_reliability.tex",
        caption="Experiment 4 audit reliability for the primary Proxy-label route.",
        label="tab:exp4_audit_reliability",
        note=(
            "Notes: The primary route uses route-label rate $0.3$ and attribution-proxy "
            "noise standard deviation $0.25$. The audit-evidence rate varies independently. "
            "The calibrated population target is conditional on fold-specific affine maps. "
            "$n_{\\mathrm{eff}}$ and $\\omega_M$ summarize evidence support and are not "
            "probabilities of route validity."
        ),
    )

    boundary_primary = boundary[
        (boundary["route_id"] == "proxy_label")
        & (boundary["analysis_tier"] == "primary")
    ].copy()
    boundary_columns = [
        "route_label_rate",
        "attribution_proxy_noise_sd",
        "population_raw_action_gap_defect_mean",
        "population_raw_action_gap_defect_ci_lower",
        "population_raw_action_gap_defect_ci_upper",
        "ranking_reversal_rate_mean",
        "margin_preservation_rate_mean",
        "structural_regret_per_round_mean",
    ]
    boundary_primary[boundary_columns].to_csv(
        tables / "tbl_app_exp4_route_boundary_values.csv", index=False
    )

    four_route = boundary[
        np.isclose(boundary["route_label_rate"], config.PARAMETERS.route_label_rate_primary_audit)
        & np.isclose(
            boundary["attribution_proxy_noise_sd"],
            config.PARAMETERS.attribution_proxy_noise_sd_primary_audit,
        )
    ].drop_duplicates("route_id")
    four_route[
        [
            "route_id",
            "population_raw_action_gap_defect_mean",
            "ranking_reversal_rate_mean",
            "margin_preservation_rate_mean",
            "structural_regret_per_round_mean",
        ]
    ].to_csv(tables / "tbl_app_exp4_four_route_audit.csv", index=False)

    controls.to_csv(tables / "tbl_app_exp4_calibration_controls.csv", index=False)
    support[support["route_id"] == "proxy_label"].to_csv(
        tables / "tbl_app_exp4_effective_support.csv", index=False
    )
    learner_summary = (
        learner.groupby(
            ["route_id", "route_label_rate", "attribution_proxy_noise_sd"],
            dropna=False,
        )
        .agg(
            seed_count=("seed", "nunique"),
            structural_regret_per_round_mean=("structural_regret_per_round", "mean"),
            structural_regret_per_round_sd=("structural_regret_per_round", "std"),
        )
        .reset_index()
    )
    learner_summary.to_csv(
        tables / "tbl_app_exp4_learner_consequence.csv", index=False
    )

    metric_definitions = pd.DataFrame(
        [
            {
                "metric_id": "population_raw_action_gap_defect",
                "definition": r"$(T-W)^{-1}\sum_t\max_{a<b}|G_t^r(a,b)-G_t^c(a,b)|$",
                "role": "Module A primary alignment target",
            },
            {
                "metric_id": "sample_calibrated_action_gap_defect",
                "definition": "Weighted mean of held-out pairwise affine-calibration residual defects",
                "role": "Calibration-family-specific audit diagnostic",
            },
            {
                "metric_id": "estimated_recoverability",
                "definition": r"$1-\widehat d_{cal}/\widehat d_{raw}$",
                "role": "Relative discrepancy reduction; not route validity",
            },
            {
                "metric_id": "effective_labelled_sample_size",
                "definition": r"$(\sum_i v_i)^2/\sum_i v_i^2$",
                "role": "Evidence support",
            },
            {
                "metric_id": "labelled_support_coefficient",
                "definition": r"$\log(1+n_{eff})/\log(1+M)$",
                "role": "Relative audit support; not a confidence level",
            },
        ]
    )
    metric_definitions.to_csv(
        tables / "tbl_app_exp4_metric_definitions.csv", index=False
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    arguments = parser.parse_args()
    run(arguments.run_dir)

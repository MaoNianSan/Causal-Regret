"""Exp4 v3 presentation-only renderer over frozen full-run summaries."""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from presentation.common import (
    PreviewLayout,
    assert_no_suptitle,
    configure_matplotlib,
    standardize_long_form,
    write_figure_bundle,
)
from presentation.renderers import figure_metadata, write_manifest, write_standard_table
from presentation_sources import PresentationSource


AUDIT_DESIGNS = [
    ("mcar_unweighted", "#1f4e79", "o"),
    ("ambiguity_selective_unweighted", "#b54708", "s"),
    ("ambiguity_selective_ipw", "#2e7d32", "^"),
]
SIGMA_PROXY_MARKERS = {
    0.0: "o",
    0.1: "s",
    0.25: "^",
    1.0: "D",
}
CALIBRATION_CONTROLS = ["affine_linked", "blocked_correspondence_destroyed"]
MAIN_CONTRACT = {
    "layout": [2, 2],
    "canvas_inches": [7.1, 5.1],
    "panel_a_source_fields": [
        "mean_pairwise_gap_discrepancy_mean",
        "mean_pairwise_gap_discrepancy_ci_lower",
        "mean_pairwise_gap_discrepancy_ci_upper",
    ],
    "panel_a_marker_registry": {str(sigma): marker for sigma, marker in SIGMA_PROXY_MARKERS.items()},
    "panel_a_exclusions": [
        "population_action_gap_defect_mean",
        "mean_round_max_gap_defect_mean",
    ],
    "panel_b": "bias +/- 1.96 MCSE",
    "panel_c": "rmse +/- 1.96 MCSE",
    "panel_d_controls": CALIBRATION_CONTROLS,
    "main_exclusions": ["effective_support"],
}


def build_main_long_form(
    boundary: pd.DataFrame,
    audit: pd.DataFrame,
    controls: pd.DataFrame,
    source: PresentationSource,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for index, row in boundary.iterrows():
        deterministic = row.route_label_rate == 1
        rows.append(
            {
                "panel_id": "a",
                "metric_id": "mean_pairwise_gap_discrepancy_mean",
                "estimand_id": "D_pair",
                "condition_id": f"q_route={row.route_label_rate:g}",
                "series_id": f"sigma_proxy={row.attribution_proxy_noise_sd:g}",
                "point_estimate": row.mean_pairwise_gap_discrepancy_mean,
                "interval_lower": pd.NA if deterministic else row.mean_pairwise_gap_discrepancy_ci_lower,
                "interval_upper": pd.NA if deterministic else row.mean_pairwise_gap_discrepancy_ci_upper,
                "uncertainty_role": "deterministic controlled endpoint" if deterministic else "paired-seed interval from frozen summary",
                "uncertainty_method": "none" if deterministic else "frozen paired-seed summary",
                "sample_count": row.shared_seed_count,
                "unit": "gap discrepancy",
                "better_direction": "lower",
                "source_table": "exp4_module_a_population_summary.csv",
                "source_row_key": str(index),
            }
        )
    selected_designs = {design for design, _, _ in AUDIT_DESIGNS} | {"full_population"}
    for index, row in audit[audit.audit_design_id.isin(selected_designs)].iterrows():
        deterministic = row.audit_design_id == "full_population"
        for panel_id, metric in (("b", "bias"), ("c", "rmse")):
            estimate = row[metric]
            mcse = row[f"{metric}_mcse"]
            rows.append(
                {
                    "panel_id": panel_id,
                    "metric_id": metric,
                    "estimand_id": metric,
                    "condition_id": f"rho_audit={row.audit_evidence_rate:g}",
                    "series_id": row.audit_design_id,
                    "point_estimate": estimate,
                    "interval_lower": pd.NA if deterministic else estimate - 1.96 * mcse,
                    "interval_upper": pd.NA if deterministic else estimate + 1.96 * mcse,
                    "uncertainty_role": "deterministic full-population endpoint" if deterministic else "estimate +/- 1.96 Monte Carlo standard error",
                    "uncertainty_method": "none" if deterministic else "1.96 x MCSE",
                    "repetition_count": row.monte_carlo_replications,
                    "unit": "audit error",
                    "better_direction": "toward zero" if metric == "bias" else "lower",
                    "source_table": "exp4_module_b_audit_performance.csv",
                    "source_row_key": str(index),
                }
            )
    selected_controls = controls[controls.control_id.isin(CALIBRATION_CONTROLS)]
    for index, row in selected_controls.iterrows():
        for series_id, column in (
            ("raw_pairwise_discrepancy", "raw_pairwise_discrepancy"),
            ("oof_calibrated_pairwise_discrepancy", "oof_calibrated_pairwise_discrepancy"),
        ):
            rows.append(
                {
                    "panel_id": "d",
                    "metric_id": column,
                    "estimand_id": "calibration_control_discrepancy",
                    "condition_id": row.control_id,
                    "series_id": series_id,
                    "point_estimate": row[column],
                    "uncertainty_role": "controlled calibration summary",
                    "uncertainty_method": "none",
                    "repetition_count": row.monte_carlo_replications,
                    "unit": "pairwise discrepancy",
                    "better_direction": "lower",
                    "source_table": "exp4_module_c_control_summary.csv",
                    "source_row_key": str(index),
                }
            )
        rows.append(
            {
                "panel_id": "d",
                "metric_id": "recoverability",
                "estimand_id": "recoverability",
                "condition_id": row.control_id,
                "series_id": "annotation",
                "point_estimate": row.recoverability,
                "uncertainty_role": "annotation",
                "uncertainty_method": "none",
                "source_table": "exp4_module_c_control_summary.csv",
                "source_row_key": str(index),
            }
        )
    return standardize_long_form(
        pd.DataFrame(rows),
        figure_id=source.main_figure_id,
        experiment_id=source.experiment_id,
        run_id=source.run_id,
        run_tier=source.run_tier,
        paper_result=False,
    )


def _metadata(
    source: PresentationSource,
    *,
    claim: str,
    panels: dict[str, str],
    metrics: dict[str, str],
    boundary: str,
    contract: dict[str, Any],
    uncertainty: str,
    sample_count: Any = "NA",
    marker_semantics: dict[str, str] | None = None,
) -> dict[str, Any]:
    return figure_metadata(
        source,
        claim=claim,
        panels=panels,
        metrics=metrics,
        boundary=boundary,
        code_paths=[Path(__file__)],
        contract=contract,
        sample_count=sample_count,
        uncertainty=uncertainty,
        marker_semantics=marker_semantics,
    )


def _appendix_composite(
    source: PresentationSource,
    layout: PreviewLayout,
    *,
    figure_id: str,
    title: str,
    paths: list[Path],
) -> None:
    fig, axes = plt.subplots(1, len(paths), figsize=(7.1, 3.1), constrained_layout=True, squeeze=False)
    long_rows: list[dict[str, Any]] = []
    for panel_index, path in enumerate(paths):
        frame = pd.read_csv(path)
        axis = axes[0, panel_index]
        plotted: list[tuple[int, str, float]] = []
        if figure_id == "exp4_appendix_route_alignment_detail" and panel_index < 2:
            metric = (
                "mean_pairwise_gap_discrepancy_mean"
                if panel_index == 0
                else "route_optimal_set_conflict_rate_mean"
            )
            matrix = frame.pivot_table(
                index="attribution_proxy_noise_sd",
                columns="route_label_rate",
                values=metric,
                aggfunc="first",
            )
            image = axis.imshow(matrix.to_numpy(float), aspect="auto", cmap="viridis")
            axis.set_xticks(np.arange(len(matrix.columns)), [f"{value:g}" for value in matrix.columns])
            axis.set_yticks(np.arange(len(matrix.index)), [f"{value:g}" for value in matrix.index])
            axis.set_xlabel(r"$q_{route}$")
            axis.set_ylabel(r"$\sigma_{proxy}$")
            fig.colorbar(image, ax=axis, label="D_pair" if panel_index == 0 else "Optimal-set conflict")
            plotted = [(index, metric, float(row[metric])) for index, row in frame.iterrows()]
        elif figure_id == "exp4_appendix_route_alignment_detail":
            metric = "mean_pairwise_gap_discrepancy_mean"
            for (dgp, sigma), group in frame.groupby(["dgp", "attribution_proxy_noise_sd"], sort=True):
                group = group.sort_values("route_label_rate")
                axis.plot(group.route_label_rate, group[metric], marker="o", linewidth=0.8, label=f"{dgp}, sigma={sigma:g}")
            axis.set_xlabel(r"$q_{route}$")
            axis.set_ylabel("D_pair")
            axis.legend(frameon=False, fontsize=6.0)
            plotted = [(index, metric, float(row[metric])) for index, row in frame.iterrows()]
        elif figure_id == "exp4_appendix_audit_support":
            metric = (
                "mean_effective_to_labelled_ratio"
                if panel_index == 0
                else "mean_weight_p95"
                if panel_index == 1
                else "rmse"
            )
            for design, group in frame.groupby("audit_design_id", sort=True):
                group = group.sort_values("audit_evidence_rate")
                axis.plot(group.audit_evidence_rate, group[metric], marker="o", linewidth=0.8, label=design.replace("_", " "))
            axis.set_xlabel(r"$\rho_{audit}$")
            axis.set_ylabel(metric.replace("_", " "))
            axis.legend(frameon=False, fontsize=5.8)
            plotted = [(index, metric, float(row[metric])) for index, row in frame.iterrows()]
        elif panel_index == 0:
            for position, (index, row) in enumerate(frame.iterrows()):
                axis.plot([row.pre_mean_abs_spearman, row.post_mean_abs_spearman], [position, position], color="0.45")
                axis.plot(row.pre_mean_abs_spearman, position, marker="o", color="#b54708")
                axis.plot(row.post_mean_abs_spearman, position, marker="s", markerfacecolor="white", markeredgecolor="#2e7d32")
                plotted.extend([(index, "pre_mean_abs_spearman", float(row.pre_mean_abs_spearman)), (index, "post_mean_abs_spearman", float(row.post_mean_abs_spearman))])
            axis.set_yticks(np.arange(len(frame)), frame.control_id)
            axis.set_xlabel("Mean absolute Spearman correspondence")
        elif panel_index == 1:
            axis.scatter(frame.true_value, frame.mean_estimate, color="#1f4e79", marker="o")
            bounds = [min(frame.true_value.min(), frame.mean_estimate.min()), max(frame.true_value.max(), frame.mean_estimate.max())]
            axis.plot(bounds, bounds, color="0.55", linestyle="--", linewidth=0.7)
            axis.set_xlabel("True parameter")
            axis.set_ylabel("Mean estimate")
            plotted = [(index, "mean_estimate", float(row.mean_estimate)) for index, row in frame.iterrows()]
        else:
            for position, (index, row) in enumerate(frame.iterrows()):
                axis.plot([row.raw_pairwise_discrepancy, row.oof_calibrated_pairwise_discrepancy], [position, position], color="0.45")
                axis.plot(row.raw_pairwise_discrepancy, position, marker="o", color="#b54708")
                axis.plot(row.oof_calibrated_pairwise_discrepancy, position, marker="s", markerfacecolor="white", markeredgecolor="#2e7d32")
                plotted.extend([(index, "raw_pairwise_discrepancy", float(row.raw_pairwise_discrepancy)), (index, "oof_calibrated_pairwise_discrepancy", float(row.oof_calibrated_pairwise_discrepancy))])
            axis.set_yticks(np.arange(len(frame)), frame.control_id)
            axis.set_xlabel("Pairwise discrepancy")
        for source_index, metric, value in plotted:
                long_rows.append(
                    {
                        "panel_id": chr(ord("a") + panel_index),
                        "metric_id": metric,
                        "estimand_id": "D_pair" if metric == "mean_pairwise_gap_discrepancy_mean" else metric,
                        "condition_id": path.stem,
                        "series_id": metric,
                        "point_estimate": value,
                        "uncertainty_role": "frozen appendix diagnostic",
                        "uncertainty_method": "source table",
                        "source_table": path.name,
                        "source_row_key": str(source_index),
                    }
                )
        axis.set_title(path.stem.replace("exp4_", "").replace("fig_app_", "").replace("_data", "").replace("_", " ").title(), loc="left", fontweight="bold")
        axis.grid(axis="y", alpha=0.2)
    assert_no_suptitle(fig)
    long_frame = standardize_long_form(
        pd.DataFrame(long_rows),
        figure_id=figure_id,
        experiment_id=source.experiment_id,
        run_id=source.run_id,
        run_tier=source.run_tier,
        paper_result=False,
        analysis_tier="appendix",
    )
    write_figure_bundle(
        fig,
        long_frame,
        layout,
        figure_id=figure_id,
        section="appendix",
        metadata=_metadata(
            source,
            claim=title,
            panels={chr(ord("a") + index): path.stem for index, path in enumerate(paths)},
            metrics={},
            boundary="Appendix composite; any round-max gap defect is secondary and is never labeled D_pair.",
            contract={"layout": [1, len(paths)], "sources": [path.name for path in paths]},
            uncertainty="Frozen diagnostic",
        ),
        source_files=paths,
    )


def render_presentation(
    source: PresentationSource, preview_root: Path
) -> dict[str, Any]:
    configure_matplotlib()
    layout = PreviewLayout(preview_root, source.experiment_id, source.run_id)
    module_a = source.source_run / "derived/module_a/exp4_module_a_population_summary.csv"
    performance = source.source_run / "derived/module_b/exp4_module_b_audit_performance.csv"
    controls_path = source.source_run / "derived/module_c/exp4_module_c_control_summary.csv"
    boundary = pd.read_csv(module_a)
    audit = pd.read_csv(performance)
    controls = pd.read_csv(controls_path)
    fig, axes = plt.subplots(2, 2, figsize=(7.1, 5.1), constrained_layout=True)

    for sigma, group in boundary.groupby("attribution_proxy_noise_sd", sort=True):
        group = group.sort_values("route_label_rate")
        uncertain = group[group.route_label_rate.lt(1)]
        color = plt.cm.viridis(float(sigma) / max(float(boundary.attribution_proxy_noise_sd.max()), 1.0))
        marker = SIGMA_PROXY_MARKERS.get(float(sigma), "o")
        axes[0, 0].errorbar(
            uncertain.route_label_rate,
            uncertain.mean_pairwise_gap_discrepancy_mean,
            yerr=[
                uncertain.mean_pairwise_gap_discrepancy_mean - uncertain.mean_pairwise_gap_discrepancy_ci_lower,
                uncertain.mean_pairwise_gap_discrepancy_ci_upper - uncertain.mean_pairwise_gap_discrepancy_mean,
            ],
            color=color,
            marker=marker,
            markerfacecolor=color,
            markeredgecolor=color,
            linewidth=0.9,
            capsize=2,
            label=rf"$\sigma={sigma:g}$",
        )
        endpoint = group[group.route_label_rate.eq(1)]
        if not endpoint.empty:
            axes[0, 0].plot(
                1,
                endpoint.mean_pairwise_gap_discrepancy_mean.iloc[0],
                marker=marker,
                markerfacecolor="white",
                markeredgecolor=color,
                color=color,
                linestyle="none",
            )
    axes[0, 0].set_xlabel(r"Route-label retention, $q_{route}$")
    axes[0, 0].set_ylabel(r"Mean pairwise gap discrepancy, $D_{pair}$")
    axes[0, 0].set_title("(a) Route alignment", loc="left", fontweight="bold")
    axes[0, 0].legend(frameon=False, fontsize=6.5)
    axes[0, 0].grid(axis="y", alpha=0.2)

    for axis, metric, title in (
        (axes[0, 1], "bias", "(b) Audit bias"),
        (axes[1, 0], "rmse", "(c) Audit RMSE"),
    ):
        for design, color, marker in AUDIT_DESIGNS:
            group = audit[
                audit.audit_design_id.eq(design) & audit.audit_evidence_rate.lt(1)
            ].sort_values("audit_evidence_rate")
            axis.errorbar(
                group.audit_evidence_rate,
                group[metric],
                yerr=1.96 * group[f"{metric}_mcse"],
                color=color,
                marker=marker,
                linewidth=0.9,
                capsize=2,
                label=design.replace("_", " "),
            )
        full = audit[audit.audit_design_id.eq("full_population")]
        axis.plot(1, full[metric].iloc[0], marker="D", color="black")
        axis.set_xlabel(r"Audit-evidence rate, $\rho_{audit}$")
        axis.set_ylabel(metric.upper())
        axis.set_title(title, loc="left", fontweight="bold")
        axis.grid(axis="y", alpha=0.2)
    axes[0, 1].axhline(0, color="0.55", linestyle="--", linewidth=0.7)

    selected_controls = controls.set_index("control_id").reindex(CALIBRATION_CONTROLS).reset_index()
    for position, row in selected_controls.iterrows():
        yi = 1 - position
        axes[1, 1].plot(
            [row.raw_pairwise_discrepancy, row.oof_calibrated_pairwise_discrepancy],
            [yi, yi],
            color="0.45",
            linewidth=0.9,
        )
        axes[1, 1].plot(row.raw_pairwise_discrepancy, yi, marker="o", color="#b54708")
        axes[1, 1].plot(
            row.oof_calibrated_pairwise_discrepancy,
            yi,
            marker="s",
            markerfacecolor="white",
            markeredgecolor="#2e7d32",
            color="#2e7d32",
        )
        axes[1, 1].text(
            0.98,
            yi,
            f"{row.recoverability:.3f}",
            transform=axes[1, 1].get_yaxis_transform(),
            ha="right",
            va="center",
            fontsize=7,
        )
    axes[1, 1].set_yticks([1, 0], CALIBRATION_CONTROLS)
    axes[1, 1].set_xlabel("Pairwise discrepancy")
    axes[1, 1].set_title("(d) Calibration-family recoverability", loc="left", fontweight="bold")
    axes[1, 1].grid(axis="x", alpha=0.2)
    assert_no_suptitle(fig)

    main = write_figure_bundle(
        fig,
        build_main_long_form(boundary, audit, controls, source),
        layout,
        figure_id=source.main_figure_id,
        section="main",
        metadata=_metadata(
            source,
            claim="Population route alignment, audit reliability, and calibration-family recoverability are distinct diagnostics.",
            panels={
                "a": "D_pair across q_route and sigma_proxy.",
                "b": "Audit bias with estimate +/- 1.96 MCSE.",
                "c": "Audit RMSE with estimate +/- 1.96 MCSE.",
                "d": "Raw versus out-of-fold calibrated pairwise discrepancy.",
            },
            metrics={
                "mean_pairwise_gap_discrepancy_mean": "D_pair",
                "bias": "Audit bias",
                "rmse": "Audit RMSE",
                "recoverability": "Recoverability",
            },
            boundary="Population alignment, audit reliability, and calibratability are distinct; lower calibrated discrepancy does not prove route validity.",
            contract=MAIN_CONTRACT,
            sample_count="100 seeds / 1000 Monte Carlo replications",
            uncertainty="Panel a paired-seed interval; panels b/c estimate +/- 1.96 MCSE; q=1 and full-population endpoints are deterministic",
            marker_semantics={
                "open_diamond": "deterministic controlled endpoint",
                "filled_markers": "full-sample audit estimates or raw discrepancy",
                "open_square": "out-of-fold calibrated discrepancy",
                "shape": "audit design and calibration role",
                "sigma_proxy_marker_registry": {str(sigma): marker for sigma, marker in SIGMA_PROXY_MARKERS.items()},
                "sigma_proxy_q1_endpoint": "open version of the sigma marker",
            },
        ),
        source_files=[module_a, performance, controls_path],
    )

    weights = source.source_run / "derived/module_b/exp4_module_b_weight_diagnostics.csv"
    appendix_groups = [
        (
            "exp4_appendix_route_alignment_detail",
            "Route-alignment detail",
            [
                module_a,
                source.source_run / "figures/data/fig_app_exp4_route_optimal_set_conflict_data.csv",
                source.source_run / "figures/data/fig_app_exp4_smooth_loss_robustness_data.csv",
            ],
        ),
        (
            "exp4_appendix_audit_support",
            "Audit support",
            [
                source.source_run / "figures/data/fig_app_exp4_effective_support_data.csv",
                weights,
                performance,
            ],
        ),
        (
            "exp4_appendix_calibration_diagnostics",
            "Calibration diagnostics",
            [
                source.source_run / "derived/module_c/exp4_module_c_correspondence_checks.csv",
                source.source_run / "derived/module_c/exp4_module_c_parameter_recovery.csv",
                controls_path,
            ],
        ),
    ]
    for figure_id, title, paths in appendix_groups:
        _appendix_composite(
            source, layout, figure_id=figure_id, title=title, paths=paths
        )
    for filename, stem, semantics in (
        ("tbl_app_exp4_parameters.csv", "tbl_app_exp4_parameters", "Frozen v3 parameter table."),
        ("tbl_app_exp4_paired_contrasts.csv", "tbl_app_exp4_paired_contrasts", "Complete Module-A D_pair and secondary diagnostic table."),
        ("tbl_app_exp4_audit_performance.csv", "tbl_app_exp4_audit_performance", "Complete audit-performance table."),
        ("tbl_exp4_calibration_controls.csv", "tbl_exp4_calibration_controls", "Calibration-control table."),
    ):
        write_standard_table(
            layout,
            source.source_run / "tables" / filename,
            stem,
            semantics=semantics,
        )
    appendix_ids = [item[0] for item in appendix_groups]
    write_manifest(layout, source, figure_ids=[source.main_figure_id])
    write_manifest(layout, source, appendix=True, figure_ids=appendix_ids)
    return {"layout": layout, "main": main, "appendix_ids": appendix_ids}


__all__ = ["MAIN_CONTRACT", "SIGMA_PROXY_MARKERS", "build_main_long_form", "render_presentation"]

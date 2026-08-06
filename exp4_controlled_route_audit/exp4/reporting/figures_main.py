"""Four-panel main figure generated only from v2 derived summaries."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from exp4.configuration.parameters import MODULE_A, REPORTING
from exp4.configuration.registries import AUDIT_DESIGN_REGISTRY
from exp4.configuration.schema import MAIN_FIGURE_ID
from exp4.reporting.figure_bundle import save_figure_bundle
from exp4.reporting.plot_style import (
    AUDIT_COLORS,
    AUDIT_MARKERS,
    NOISE_COLORS,
    NOISE_MARKERS,
    set_publication_style,
)


def _plot_route_boundary(axis: plt.Axes, boundary: pd.DataFrame) -> None:
    primary = boundary[boundary["route_id"] == "proxy_label"]
    for sigma in MODULE_A.proxy_noise_sds:
        group = primary[np.isclose(primary["attribution_proxy_noise_sd"], sigma)].sort_values(
            "route_label_rate"
        )
        finite = group[group["route_label_rate"] < 1.0]
        x = finite["route_label_rate"].to_numpy(float)
        y = finite["population_action_gap_defect_mean"].to_numpy(float)
        lower = finite["population_action_gap_defect_ci_lower"].to_numpy(float)
        upper = finite["population_action_gap_defect_ci_upper"].to_numpy(float)
        if np.all(np.isfinite(lower)) and np.all(np.isfinite(upper)):
            axis.errorbar(
                x,
                y,
                yerr=np.vstack((y - lower, upper - y)),
                color=NOISE_COLORS[sigma],
                marker=NOISE_MARKERS[sigma],
                linewidth=1.1,
                capsize=2,
                label=rf"$\sigma={sigma:g}$",
            )
        else:
            axis.plot(
                x,
                y,
                color=NOISE_COLORS[sigma],
                marker=NOISE_MARKERS[sigma],
                linewidth=1.1,
                label=rf"$\sigma={sigma:g}$",
            )
        q1 = group[np.isclose(group["route_label_rate"], 1.0)]
        axis.plot(
            [float(x[-1]), 1.0],
            [float(y[-1]), float(q1["population_action_gap_defect_mean"].iloc[0])],
            color=NOISE_COLORS[sigma],
            linewidth=1.1,
        )
        axis.scatter(
            [1.0],
            [float(q1["population_action_gap_defect_mean"].iloc[0])],
            marker="D",
            facecolors="none",
            edgecolors=NOISE_COLORS[sigma],
            linewidths=1.0,
            zorder=4,
        )
    axis.annotate(
        "controlled invariant",
        xy=(1.0, 0.0),
        xytext=(-5, 12),
        textcoords="offset points",
        ha="right",
        fontsize=6.5,
    )
    axis.set_xlabel(r"Route-label retention, $q_{route}$")
    axis.set_ylabel("Population action-gap defect")
    axis.set_xticks(MODULE_A.route_label_rates)
    axis.set_ylim(bottom=0.0)
    axis.grid(axis="y")
    axis.legend(frameon=False, ncol=2)


def _plot_audit_metric(axis: plt.Axes, performance: pd.DataFrame, metric: str) -> None:
    finite = performance[performance["audit_evidence_rate"] < 1.0]
    for design_id in (
        "mcar_unweighted",
        "ambiguity_selective_unweighted",
        "ambiguity_selective_ipw",
    ):
        group = finite[finite["audit_design_id"] == design_id].sort_values(
            "audit_evidence_rate"
        )
        axis.errorbar(
            group["audit_evidence_rate"],
            group[metric],
            yerr=1.96 * group[f"{metric}_mcse"],
            color=AUDIT_COLORS[design_id],
            marker=AUDIT_MARKERS[design_id],
            linewidth=1.1,
            capsize=2,
            label=AUDIT_DESIGN_REGISTRY[design_id]["display_name"],
        )
    full = performance[performance["audit_design_id"] == "full_population"]
    axis.scatter(
        [1.0],
        [float(full[metric].iloc[0])],
        color="black",
        marker="D",
        s=22,
        zorder=5,
        label="Full-population audit",
    )
    axis.set_xticks((0.1, 0.3, 0.5, 1.0))
    axis.set_xlabel(r"Audit-evidence rate, $\rho_{audit}$")
    axis.grid(axis="y")


def plot_main_figure(run_dir: Path) -> None:
    set_publication_style()
    boundary_path = run_dir / "derived" / "module_a" / "exp4_module_a_population_summary.csv"
    performance_path = run_dir / "derived" / "module_b" / "exp4_module_b_audit_performance.csv"
    support_path = run_dir / "derived" / "module_b" / "exp4_module_b_weight_diagnostics.csv"
    boundary = pd.read_csv(boundary_path)
    performance = pd.read_csv(performance_path)
    support = pd.read_csv(support_path)
    figure, axes = plt.subplots(
        2,
        2,
        figsize=(REPORTING.paper_figure_width_in, REPORTING.paper_figure_height_in),
    )
    _plot_route_boundary(axes[0, 0], boundary)
    _plot_audit_metric(axes[0, 1], performance, "bias")
    axes[0, 1].axhline(0.0, color="0.4", linestyle="--", linewidth=0.8)
    axes[0, 1].set_ylabel("Audit bias")
    _plot_audit_metric(axes[1, 0], performance, "rmse")
    axes[1, 0].set_ylabel("Audit RMSE")
    finite_support = support[support["audit_evidence_rate"] < 1.0]
    for design_id in (
        "mcar_unweighted",
        "ambiguity_selective_unweighted",
        "ambiguity_selective_ipw",
    ):
        group = finite_support[finite_support["audit_design_id"] == design_id].sort_values(
            "audit_evidence_rate"
        )
        axes[1, 1].plot(
            group["audit_evidence_rate"],
            group["mean_effective_to_labelled_ratio"],
            color=AUDIT_COLORS[design_id],
            marker=AUDIT_MARKERS[design_id],
            linewidth=1.1,
            label=AUDIT_DESIGN_REGISTRY[design_id]["display_name"],
        )
    axes[1, 1].scatter([1.0], [1.0], color="black", marker="D", s=22, zorder=5)
    axes[1, 1].set_xlabel(r"Audit-evidence rate, $\rho_{audit}$")
    axes[1, 1].set_ylabel(r"Effective support, $n_{eff}/n_{lab}$")
    axes[1, 1].set_xticks((0.1, 0.3, 0.5, 1.0))
    axes[1, 1].set_ylim(0.0, 1.05)
    axes[1, 1].grid(axis="y")
    titles = (
        "(a) Population route-alignment boundary",
        "(b) Audit bias",
        "(c) Audit RMSE",
        "(d) Effective support",
    )
    for axis, title in zip(axes.flat, titles, strict=True):
        axis.set_title(title, loc="left", fontweight="bold", pad=6)
    handles, labels = axes[0, 1].get_legend_handles_labels()
    figure.legend(handles, labels, frameon=False, loc="lower center", ncol=2)
    figure.subplots_adjust(left=0.09, right=0.98, top=0.95, bottom=0.16, wspace=0.34, hspace=0.38)
    figure_data = pd.concat(
        (
            boundary.assign(panel="a_route_alignment"),
            performance.assign(panel="b_c_audit_performance"),
            support.assign(panel="d_effective_support"),
        ),
        ignore_index=True,
        sort=False,
    )
    save_figure_bundle(
        figure,
        run_dir,
        MAIN_FIGURE_ID,
        figure_data,
        [boundary_path, performance_path, support_path],
        {
            "panel_definitions": {
                "a": "Population action-gap defect across shared structural seeds.",
                "b": "Monte Carlo bias of the population-defect audit estimator.",
                "c": "Monte Carlo RMSE of the population-defect audit estimator.",
                "d": "Effective support relative to labelled support.",
            },
            "uncertainty_definition": (
                "Panel a uses paired-seed bootstrap when enabled; panels b and c use "
                "Monte Carlo standard errors. Endpoints q=1 and rho=1 are controlled invariants."
            ),
            "deterministic_endpoints": {"q_route_1": True, "rho_audit_1": True},
        },
    )

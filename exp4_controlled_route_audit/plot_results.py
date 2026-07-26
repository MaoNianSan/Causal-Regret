"""Paper-facing figures generated only from frozen derived outputs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

import config
from io_utils import file_hash_mapping, write_json

ROUTE_COLORS = {
    "arrival_time": "#4C4C4C",
    "history_surrogate": "#7A6F5D",
    "proxy_label": "#2D6A8A",
    "source_bound": "#8A3F5D",
}
AUDIT_COLORS = {
    "mcar_unweighted": "#4C78A8",
    "ambiguity_biased_unweighted": "#E07B39",
    "ambiguity_biased_ipw": "#5A9E6F",
}
AUDIT_MARKERS = {
    "mcar_unweighted": "o",
    "ambiguity_biased_unweighted": "s",
    "ambiguity_biased_ipw": "^",
}
NOISE_MARKERS = {0.10: "o", 0.25: "s", 1.00: "^"}
NOISE_LINESTYLES = {0.10: "-", 0.25: "--", 1.00: ":"}
NOISE_COLORS = {0.10: "#2D6A8A", 0.25: "#7A6F5D", 1.00: "#A84F3D"}


def _set_publication_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": config.TICK_FONT_SIZE,
            "axes.labelsize": config.AXIS_LABEL_FONT_SIZE,
            "axes.titlesize": config.TITLE_FONT_SIZE,
            "xtick.labelsize": config.TICK_FONT_SIZE,
            "ytick.labelsize": config.TICK_FONT_SIZE,
            "legend.fontsize": config.LEGEND_FONT_SIZE,
            "axes.linewidth": 0.8,
            "grid.linewidth": 0.5,
            "grid.alpha": 0.25,
            "savefig.bbox": "tight",
        }
    )


def _errorbar(
    axis: plt.Axes,
    x: np.ndarray,
    y: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    **kwargs: Any,
) -> None:
    if np.all(np.isnan(lower)) or np.all(np.isnan(upper)):
        axis.plot(x, y, **kwargs)
        return
    yerr = np.vstack([y - lower, upper - y])
    axis.errorbar(x, y, yerr=yerr, capsize=2.2, **kwargs)



def _bar_with_zero_markers(
    axis: plt.Axes,
    x: np.ndarray,
    values: np.ndarray,
    colors: list[str],
    *,
    lower: np.ndarray | None = None,
    upper: np.ndarray | None = None,
    zero_label_format: str = "0",
) -> None:
    """Draw bars while making exact zeros visible and optionally adding CIs."""
    axis.bar(x, values, color=colors, edgecolor="0.25", linewidth=0.45, zorder=2)
    if lower is not None and upper is not None:
        finite = np.isfinite(lower) & np.isfinite(upper)
        if np.any(finite):
            yerr = np.vstack([values[finite] - lower[finite], upper[finite] - values[finite]])
            axis.errorbar(
                x[finite],
                values[finite],
                yerr=yerr,
                fmt="none",
                ecolor="0.20",
                elinewidth=0.8,
                capsize=2.0,
                zorder=3,
            )
    zero_mask = np.isclose(values, 0.0, atol=config.PARAMETERS.zero_defect_tolerance)
    if np.any(zero_mask):
        axis.scatter(
            x[zero_mask],
            np.zeros(int(np.sum(zero_mask))),
            marker="D",
            s=18,
            facecolors=np.asarray(colors, dtype=object)[zero_mask].tolist(),
            edgecolors="black",
            linewidths=0.55,
            zorder=5,
            clip_on=False,
        )
        for x_value in x[zero_mask]:
            axis.annotate(
                zero_label_format,
                xy=(x_value, 0.0),
                xytext=(0, 5),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=config.LEGEND_FONT_SIZE,
                zorder=6,
            )


def _save_figure_bundle(
    figure: plt.Figure,
    run_dir: Path,
    figure_id: str,
    figure_data: pd.DataFrame,
    source_files: list[Path],
    metadata: dict[str, Any],
) -> None:
    pdf_path = run_dir / "figures" / "pdf" / f"{figure_id}.pdf"
    png_path = run_dir / "figures" / "png" / f"{figure_id}.png"
    data_path = run_dir / "figures" / "data" / f"{figure_id}_data.csv"
    metadata_path = run_dir / "figures" / "metadata" / f"{figure_id}_metadata.json"
    figure.savefig(pdf_path)
    figure.savefig(png_path, dpi=config.PAPER_DPI)
    figure_data.to_csv(data_path, index=False)
    run_config = json.loads(
        (run_dir / "logs" / "run_config.json").read_text(encoding="utf-8")
    )
    payload = {
        "figure_id": figure_id,
        "experiment_id": config.EXPERIMENT_ID,
        "source_derived_files": [path.relative_to(run_dir).as_posix() for path in source_files],
        "source_file_hashes": file_hash_mapping(source_files),
        "code_commit": run_config["code_commit"],
        "config_hash": run_config["config_hash"],
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "run_tier": run_config["run_tier"],
        "paper_result": bool(run_config["paper_result"]),
        "route_order": config.ROUTE_ORDER,
        "confidence_level": config.PARAMETERS.confidence_level,
        **metadata,
    }
    write_json(payload, metadata_path)
    plt.close(figure)


def _expand_full_population_for_plot(audit_summary: pd.DataFrame) -> pd.DataFrame:
    proxy = audit_summary[audit_summary["route_id"] == "proxy_label"].copy()
    non_full = proxy[proxy["audit_evidence_rate"] < 1.0].copy()
    full = proxy[proxy["audit_design_id"] == "full_population"].copy()
    duplicated: list[pd.DataFrame] = [non_full]
    for design_id in [
        "mcar_unweighted",
        "ambiguity_biased_unweighted",
        "ambiguity_biased_ipw",
    ]:
        version = full.copy()
        version["audit_design_id"] = design_id
        version["inclusion_mechanism"] = config.AUDIT_DESIGN_REGISTRY[design_id][
            "inclusion_mechanism"
        ]
        version["weighting_method"] = config.AUDIT_DESIGN_REGISTRY[design_id][
            "weighting_method"
        ]
        duplicated.append(version)
    return pd.concat(duplicated, ignore_index=True)


def plot_main_figure(run_dir: Path) -> None:
    _set_publication_style()
    boundary_path = run_dir / "derived" / "exp4_route_boundary_summary.csv"
    audit_path = run_dir / "derived" / "exp4_audit_condition_summary.csv"
    control_path = run_dir / "derived" / "exp4_calibration_control_summary.csv"
    boundary = pd.read_csv(boundary_path)
    audit = pd.read_csv(audit_path)
    controls = pd.read_csv(control_path)

    figure = plt.figure(
        figsize=(config.PAPER_FIGURE_WIDTH_IN, config.PAPER_FIGURE_HEIGHT_IN)
    )
    grid = GridSpec(
        2,
        3,
        figure=figure,
        width_ratios=[1.20, 0.95, 1.10],
        wspace=0.68,
        hspace=0.58,
    )
    axis_a = figure.add_subplot(grid[:, 0])
    axis_b1 = figure.add_subplot(grid[0, 1])
    axis_b2 = figure.add_subplot(grid[1, 1])
    axis_c = figure.add_subplot(grid[:, 2])

    primary = boundary[
        (boundary["route_id"] == "proxy_label")
        & (boundary["analysis_tier"] == "primary")
    ]
    for noise_sd in config.MODULE_A_ATTRIBUTION_PROXY_NOISE_SDS:
        group = primary[
            np.isclose(primary["attribution_proxy_noise_sd"], noise_sd)
        ].sort_values("route_label_rate")
        x = group["route_label_rate"].to_numpy(dtype=float)
        y = group["population_raw_action_gap_defect_mean"].to_numpy(dtype=float)
        lower = group["population_raw_action_gap_defect_ci_lower"].to_numpy(dtype=float)
        upper = group["population_raw_action_gap_defect_ci_upper"].to_numpy(dtype=float)
        _errorbar(
            axis_a,
            x,
            y,
            lower,
            upper,
            color=NOISE_COLORS[noise_sd],
            marker=NOISE_MARKERS[noise_sd],
            linestyle=NOISE_LINESTYLES[noise_sd],
            linewidth=config.LINE_WIDTH,
            markersize=config.MARKER_SIZE,
            label=rf"$\sigma={noise_sd:g}$",
        )
    axis_a.axhline(0.0, color="0.45", linewidth=0.8, linestyle="--")
    axis_a.set_xlabel(r"Source-label retention, $q_{route}$")
    axis_a.set_ylabel("Population action-gap defect")
    axis_a.set_xticks(config.MODULE_A_ROUTE_LABEL_RATES)
    axis_a.set_ylim(bottom=0.0)
    axis_a.grid(axis="y")
    axis_a.legend(frameon=False, loc="upper right")
    axis_a.set_title("(a) Route alignment boundary", loc="left", fontweight="bold", pad=7)

    audit_plot = _expand_full_population_for_plot(audit)
    for design_id in [
        "mcar_unweighted",
        "ambiguity_biased_unweighted",
        "ambiguity_biased_ipw",
    ]:
        group = audit_plot[audit_plot["audit_design_id"] == design_id].sort_values(
            "audit_evidence_rate"
        )
        x = group["audit_evidence_rate"].to_numpy(dtype=float)
        for axis, metric in [(axis_b1, "raw_bias"), (axis_b2, "raw_rmse")]:
            y = group[metric].to_numpy(dtype=float)
            lower = group[f"{metric}_ci_lower"].to_numpy(dtype=float)
            upper = group[f"{metric}_ci_upper"].to_numpy(dtype=float)
            _errorbar(
                axis,
                x,
                y,
                lower,
                upper,
                color=AUDIT_COLORS[design_id],
                marker=AUDIT_MARKERS[design_id],
                linestyle="-",
                linewidth=config.LINE_WIDTH,
                markersize=config.MARKER_SIZE,
                label={"mcar_unweighted":"MCAR", "ambiguity_biased_unweighted":"Biased", "ambiguity_biased_ipw":"Biased + IPW"}[design_id],
            )
    axis_b1.axhline(0.0, color="0.45", linewidth=0.8, linestyle="--")
    axis_b1.set_ylabel("Signed bias")
    axis_b1.set_xticks(config.AUDIT_EVIDENCE_RATES)
    axis_b1.grid(axis="y")
    axis_b1.set_title("(b1) Signed bias", loc="left", fontweight="bold", pad=7)
    axis_b1.tick_params(labelbottom=False)
    axis_b2.set_xlabel(r"Audit-evidence rate, $\rho_{audit}$")
    axis_b2.set_ylabel("RMSE")
    axis_b2.set_xticks(config.AUDIT_EVIDENCE_RATES)
    axis_b2.set_ylim(bottom=0.0)
    axis_b2.grid(axis="y")
    axis_b2.set_title("(b2) RMSE", loc="left", fontweight="bold", pad=7)
    handles = [
        Line2D(
            [0],
            [0],
            color=AUDIT_COLORS[design_id],
            marker=AUDIT_MARKERS[design_id],
            linewidth=config.LINE_WIDTH,
            label={"mcar_unweighted":"MCAR", "ambiguity_biased_unweighted":"Biased", "ambiguity_biased_ipw":"Biased + IPW"}[design_id],
        )
        for design_id in [
            "mcar_unweighted",
            "ambiguity_biased_unweighted",
            "ambiguity_biased_ipw",
        ]
    ]
    figure.legend(handles=handles, labels=["MCAR", "Biased", "Biased + IPW"], frameon=False, loc="lower center", bbox_to_anchor=(0.52, -0.01), ncol=3, columnspacing=1.1, handletextpad=0.5)

    control_primary = controls[controls["analysis_tier"] == "primary"].copy()
    control_primary["order"] = control_primary["control_id"].map(
        {"affine_positive": 1, "shuffled_negative": 0}
    )
    control_primary = control_primary.sort_values("order")
    y_positions = np.arange(len(control_primary), dtype=float)
    for y_position, (_, row) in zip(y_positions, control_primary.iterrows(), strict=True):
        raw_mean = float(row["raw_defect_mean"])
        calibrated_mean = float(row["calibrated_defect_mean"])
        axis_c.plot(
            [raw_mean, calibrated_mean],
            [y_position, y_position],
            color="0.55",
            linewidth=1.0,
            zorder=1,
        )
        raw_lower, raw_upper = row["raw_defect_ci_lower"], row["raw_defect_ci_upper"]
        cal_lower, cal_upper = row["calibrated_defect_ci_lower"], row["calibrated_defect_ci_upper"]
        axis_c.errorbar(
            raw_mean,
            y_position,
            xerr=(
                None
                if pd.isna(raw_lower) or pd.isna(raw_upper)
                else [[raw_mean - raw_lower], [raw_upper - raw_mean]]
            ),
            fmt="o",
            color="#5B5B5B",
            capsize=2.2,
            markersize=config.MARKER_SIZE,
            label="Raw" if y_position == 0 else None,
            zorder=2,
        )
        axis_c.errorbar(
            calibrated_mean,
            y_position,
            xerr=(
                None
                if pd.isna(cal_lower) or pd.isna(cal_upper)
                else [[calibrated_mean - cal_lower], [cal_upper - calibrated_mean]]
            ),
            fmt="s",
            color="#2D6A8A",
            capsize=2.2,
            markersize=config.MARKER_SIZE,
            label="Calibrated" if y_position == 0 else None,
            zorder=3,
        )
        axis_c.annotate(
            f"Rec={row['estimated_recoverability_mean']:.2f}\nNeg={row['negative_recoverability_rate']:.2f}",
            xy=(max(raw_mean, calibrated_mean), y_position),
            xytext=(5, 0),
            textcoords="offset points",
            va="center",
            fontsize=config.LEGEND_FONT_SIZE,
        )
    axis_c.set_yticks(y_positions)
    axis_c.set_yticklabels(["Shuffled negative", "Affine positive"])
    axis_c.set_xlabel("Observed action-gap defect")
    axis_c.set_xlim(left=0.0)
    axis_c.margins(y=0.35)
    axis_c.grid(axis="x")
    axis_c.legend(frameon=False, loc="upper left")
    axis_c.set_title("(c) Calibration controls", loc="left", fontweight="bold", pad=7)

    figure_data = pd.concat(
        [
            primary.assign(panel="a_route_alignment"),
            audit_plot.assign(panel="b_audit_estimation"),
            control_primary.assign(panel="c_calibration_controls"),
        ],
        ignore_index=True,
        sort=False,
    )
    _save_figure_bundle(
        figure,
        run_dir,
        "fig_exp4_route_alignment_and_audit",
        figure_data,
        [boundary_path, audit_path, control_path],
        {
            "module_ids": [
                config.MODULE_ROUTE_BOUNDARY,
                config.MODULE_AUDIT_RELIABILITY,
                config.MODULE_CALIBRATION_CONTROL,
            ],
            "panel_definitions": {
                "a": "Population raw action-gap defect across route-label retention and attribution-proxy noise.",
                "b1": "Monte Carlo signed bias of the raw-defect estimator.",
                "b2": "Monte Carlo RMSE of the raw-defect estimator.",
                "c": "Raw and out-of-fold calibrated defects in prespecified controls.",
            },
            "axis_definitions": {
                "a_x": "route_label_rate",
                "a_y": "population_raw_action_gap_defect",
                "b_x": "audit_evidence_rate",
                "b1_y": "raw_bias",
                "b2_y": "raw_rmse",
                "c_x": "sample action-gap defect",
            },
            "uncertainty_definition": (
                "Module A uses shared-seed percentile bootstrap; Module B and controls "
                "use Monte Carlo replication bootstrap. Fast mode reports point estimates only."
            ),
            "resampling_unit": "seed for panel a; Monte Carlo replication for panels b and c",
            "bootstrap_replications": config.PARAMETERS.bootstrap_replications,
        },
    )


def plot_appendix_figures(run_dir: Path) -> None:
    _set_publication_style()
    boundary_path = run_dir / "derived" / "exp4_route_boundary_summary.csv"
    seed_path = run_dir / "derived" / "exp4_route_boundary_seed_level.parquet"
    support_path = run_dir / "derived" / "exp4_effective_support_summary.csv"
    control_rep_path = run_dir / "derived" / "exp4_calibration_control_replication_level.csv"
    learner_path = run_dir / "derived" / "exp4_learner_consequence_appendix.csv"
    boundary = pd.read_csv(boundary_path)
    seed_level = pd.read_parquet(seed_path)
    support = pd.read_csv(support_path)
    controls = pd.read_csv(control_rep_path)
    learner = pd.read_csv(learner_path)

    # Heatmap of exact primary route-boundary values.
    primary = boundary[(boundary["route_id"] == "proxy_label") & (boundary["analysis_tier"] == "primary")]
    matrix = primary.pivot(
        index="attribution_proxy_noise_sd",
        columns="route_label_rate",
        values="population_raw_action_gap_defect_mean",
    ).reindex(
        index=config.MODULE_A_ATTRIBUTION_PROXY_NOISE_SDS,
        columns=config.MODULE_A_ROUTE_LABEL_RATES,
    )
    figure, axis = plt.subplots(figsize=(5.0, 2.7))
    image = axis.imshow(matrix.to_numpy(), aspect="auto", vmin=0.0, cmap="viridis")
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            axis.text(column, row, f"{matrix.iloc[row, column]:.3f}", ha="center", va="center", color="white" if matrix.iloc[row, column] > matrix.to_numpy().max() * 0.55 else "black")
    axis.set_xticks(range(matrix.shape[1]), labels=[f"{value:g}" for value in matrix.columns])
    axis.set_yticks(range(matrix.shape[0]), labels=[f"{value:g}" for value in matrix.index])
    axis.set_xlabel(r"Source-label retention, $q_{route}$")
    axis.set_ylabel(r"Proxy noise, $\sigma_{proxy}$")
    axis.set_title("Population raw action-gap defect")
    figure.colorbar(image, ax=axis, label="Defect")
    _save_figure_bundle(
        figure,
        run_dir,
        "fig_app_exp4_route_boundary_heatmap",
        primary,
        [boundary_path],
        {
            "module_ids": [config.MODULE_ROUTE_BOUNDARY],
            "panel_definitions": {"main": "Exact 4-by-3 primary route-boundary grid."},
            "axis_definitions": {"x": "route_label_rate", "y": "attribution_proxy_noise_sd"},
            "uncertainty_definition": "Intervals are reported in the companion table, not encoded in the heatmap.",
            "resampling_unit": "seed",
            "bootstrap_replications": config.PARAMETERS.bootstrap_replications,
        },
    )

    # Alignment-regret association.
    proxy_seed = seed_level[(seed_level["route_id"] == "proxy_label") & (seed_level["analysis_tier"] == "primary")]
    figure, axis = plt.subplots(figsize=(4.8, 3.2))
    for noise_sd in config.MODULE_A_ATTRIBUTION_PROXY_NOISE_SDS:
        group = proxy_seed[np.isclose(proxy_seed["attribution_proxy_noise_sd"], noise_sd)]
        axis.scatter(
            group["population_raw_action_gap_defect"],
            group["structural_regret_per_round"],
            s=16,
            alpha=0.55,
            marker=NOISE_MARKERS[noise_sd],
            color=NOISE_COLORS[noise_sd],
            label=rf"$\sigma={noise_sd:g}$",
        )
    axis.set_xlabel("Population raw action-gap defect")
    axis.set_ylabel("Route-induced structural regret per round")
    axis.set_xlim(left=0.0)
    axis.set_ylim(bottom=0.0)
    axis.grid()
    axis.legend(frameon=False)
    _save_figure_bundle(
        figure,
        run_dir,
        "fig_app_exp4_alignment_regret_association",
        proxy_seed,
        [seed_path],
        {
            "module_ids": [config.MODULE_ROUTE_BOUNDARY],
            "panel_definitions": {"main": "Descriptive association between alignment defect and route-induced structural regret."},
            "axis_definitions": {"x": "population_raw_action_gap_defect", "y": "structural_regret_per_round"},
            "uncertainty_definition": "Seed-level points; association is descriptive and not a causal response function.",
            "resampling_unit": "seed",
            "bootstrap_replications": 0,
        },
    )

    # Four-route comparison at the primary audit configuration.
    fixed = boundary[
        np.isclose(boundary["route_label_rate"], config.PARAMETERS.route_label_rate_primary_audit)
        & np.isclose(boundary["attribution_proxy_noise_sd"], config.PARAMETERS.attribution_proxy_noise_sd_primary_audit)
    ].drop_duplicates("route_id")
    fixed["route_order"] = fixed["route_id"].map({route: index for index, route in enumerate(config.ROUTE_ORDER)})
    fixed = fixed.sort_values("route_order")
    figure, axes = plt.subplots(2, 2, figsize=(6.4, 4.8))
    metrics = [
        ("population_raw_action_gap_defect_mean", "Action-gap defect"),
        ("ranking_reversal_rate_mean", "Ranking reversal rate"),
        ("margin_preservation_rate_mean", "Margin preservation rate"),
        ("structural_regret_per_round_mean", "Structural regret per round"),
    ]
    x = np.arange(len(fixed))
    route_colors = [ROUTE_COLORS[route] for route in fixed["route_id"]]
    for axis, (metric, title) in zip(axes.flat, metrics, strict=True):
        values = fixed[metric].to_numpy(dtype=float)
        ci_prefix = metric.removesuffix("_mean")
        lower_column = f"{ci_prefix}_ci_lower"
        upper_column = f"{ci_prefix}_ci_upper"
        lower = (
            fixed[lower_column].to_numpy(dtype=float)
            if lower_column in fixed.columns
            else None
        )
        upper = (
            fixed[upper_column].to_numpy(dtype=float)
            if upper_column in fixed.columns
            else None
        )
        _bar_with_zero_markers(
            axis,
            x,
            values,
            route_colors,
            lower=lower,
            upper=upper,
        )
        axis.set_xticks(
            x,
            labels=[
                config.ROUTE_REGISTRY[route]["route_display_name"]
                for route in fixed["route_id"]
            ],
            rotation=25,
            ha="right",
        )
        axis.set_title(title)
        if "preservation" not in metric:
            nonzero_max = float(np.nanmax(values)) if len(values) else 0.0
            axis.set_ylim(0.0, max(0.05, nonzero_max * 1.12))
        else:
            axis.set_ylim(0.0, 1.05)
        axis.grid(axis="y")
    figure.tight_layout()
    _save_figure_bundle(
        figure,
        run_dir,
        "fig_app_exp4_four_route_comparison",
        fixed,
        [boundary_path],
        {
            "module_ids": [config.MODULE_ROUTE_BOUNDARY],
            "panel_definitions": {"four_panels": "Four route diagnostics at q_route=0.3 and sigma_proxy=0.25."},
            "axis_definitions": {"x": "route_id", "y": "metric-specific"},
            "uncertainty_definition": "Seed means; intervals are available in derived source data.",
            "resampling_unit": "seed",
            "bootstrap_replications": config.PARAMETERS.bootstrap_replications,
        },
    )

    # Effective support.
    support_proxy = support[support["route_id"] == "proxy_label"].copy()
    support_plot = _expand_full_population_for_plot(support_proxy.rename(columns={"mean_effective_labelled_sample_size": "raw_bias", "mean_labelled_support_coefficient": "raw_rmse"}))
    # Restore names after expansion helper.
    support_plot = _expand_full_population_for_plot(
        support_proxy.assign(
            raw_bias=support_proxy["mean_effective_labelled_sample_size"],
            raw_rmse=support_proxy["mean_labelled_support_coefficient"],
        )
    )
    figure, axes = plt.subplots(1, 2, figsize=(6.3, 2.8))
    for design_id in ["mcar_unweighted", "ambiguity_biased_unweighted", "ambiguity_biased_ipw"]:
        group = support_plot[support_plot["audit_design_id"] == design_id].sort_values("audit_evidence_rate")
        axes[0].plot(group["audit_evidence_rate"], group["mean_effective_labelled_sample_size"], marker=AUDIT_MARKERS[design_id], color=AUDIT_COLORS[design_id], label=config.AUDIT_DESIGN_REGISTRY[design_id]["display_name"])
        axes[1].plot(group["audit_evidence_rate"], group["mean_labelled_support_coefficient"], marker=AUDIT_MARKERS[design_id], color=AUDIT_COLORS[design_id])
    axes[0].set_ylabel(r"Mean $n_{eff}$")
    axes[1].set_ylabel(r"Mean $\omega_M$")
    for axis in axes:
        axis.set_xlabel(r"Audit-evidence rate, $\rho_{audit}$")
        axis.set_xticks(config.AUDIT_EVIDENCE_RATES)
        axis.set_ylim(bottom=0.0)
        axis.grid()
    axes[0].legend(frameon=False)
    figure.tight_layout()
    _save_figure_bundle(
        figure,
        run_dir,
        "fig_app_exp4_effective_support",
        support_plot,
        [support_path],
        {
            "module_ids": [config.MODULE_AUDIT_RELIABILITY],
            "panel_definitions": {"left": "Effective labelled sample size.", "right": "Labelled-support coefficient."},
            "axis_definitions": {"x": "audit_evidence_rate", "left_y": "effective_labelled_sample_size", "right_y": "labelled_support_coefficient"},
            "uncertainty_definition": "Monte Carlo means.",
            "resampling_unit": "replication",
            "bootstrap_replications": 0,
        },
    )

    # Calibration distributions.
    figure, axes = plt.subplots(1, 2, figsize=(6.2, 2.8))
    control_ids = config.CONTROL_ORDER
    recovery_values = [controls.loc[controls["control_id"] == control, "estimated_recoverability"].dropna().to_numpy() for control in control_ids]
    axes[0].boxplot(recovery_values, labels=[config.CONTROL_REGISTRY[control]["display_name"] for control in control_ids], showfliers=False)
    axes[0].axhline(0.0, color="0.45", linestyle="--", linewidth=0.8)
    axes[0].set_ylabel("Estimated recoverability")
    axes[0].tick_params(axis="x", rotation=25)
    negative_rates = np.asarray(
        [float(np.mean(values < 0.0)) if len(values) else np.nan for values in recovery_values],
        dtype=float,
    )
    control_x = np.arange(len(control_ids))
    control_colors = ["#4C78A8", "#E07B39", "#7A6F5D"]
    _bar_with_zero_markers(
        axes[1],
        control_x,
        negative_rates,
        control_colors,
        zero_label_format="0.00",
    )
    axes[1].set_xticks(
        control_x,
        labels=[config.CONTROL_REGISTRY[control]["display_name"] for control in control_ids],
        rotation=25,
        ha="right",
    )
    axes[1].set_ylabel("Negative-recoverability rate")
    finite_rates = negative_rates[np.isfinite(negative_rates)]
    rate_upper = (
        max(0.10, min(1.0, float(np.max(finite_rates)) * 1.20 + 0.05))
        if len(finite_rates)
        else 1.0
    )
    axes[1].set_ylim(0.0, rate_upper)
    for axis in axes:
        axis.grid(axis="y")
    figure.tight_layout()
    _save_figure_bundle(
        figure,
        run_dir,
        "fig_app_exp4_calibration_distributions",
        controls,
        [control_rep_path],
        {
            "module_ids": [config.MODULE_CALIBRATION_CONTROL],
            "panel_definitions": {"left": "Replication distribution of estimated recoverability.", "right": "Negative-recoverability rate."},
            "axis_definitions": {"x": "control_id", "left_y": "estimated_recoverability", "right_y": "negative_recoverability_rate"},
            "uncertainty_definition": "Replication distributions; no significance testing.",
            "resampling_unit": "replication",
            "bootstrap_replications": 0,
        },
    )


def run(run_dir: Path) -> None:
    plot_main_figure(run_dir)
    plot_appendix_figures(run_dir)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    arguments = parser.parse_args()
    run(arguments.run_dir)

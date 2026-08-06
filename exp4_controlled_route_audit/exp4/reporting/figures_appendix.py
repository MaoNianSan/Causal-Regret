"""Appendix figures generated from frozen v2 derived outputs."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from exp4.configuration.parameters import MODULE_A
from exp4.configuration.schema import APPENDIX_FIGURE_IDS
from exp4.reporting.figure_bundle import save_figure_bundle
from exp4.reporting.plot_style import NOISE_COLORS, set_publication_style


def _save(
    figure: plt.Figure,
    run_dir: Path,
    figure_id: str,
    data: pd.DataFrame,
    source: Path,
    description: str,
) -> None:
    figure.tight_layout()
    save_figure_bundle(
        figure,
        run_dir,
        figure_id,
        data,
        [source],
        {"panel_definitions": {"main": description}},
    )


def _heatmap(run_dir: Path, population: pd.DataFrame, source: Path) -> None:
    primary = population[population["route_id"] == "proxy_label"]
    matrix = primary.pivot(
        index="attribution_proxy_noise_sd",
        columns="route_label_rate",
        values="population_action_gap_defect_mean",
    ).reindex(index=MODULE_A.proxy_noise_sds, columns=MODULE_A.route_label_rates)
    figure, axis = plt.subplots(figsize=(5.0, 2.8))
    image = axis.imshow(matrix.to_numpy(), aspect="auto", cmap="viridis")
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            axis.text(column, row, f"{matrix.iloc[row, column]:.3f}", ha="center", va="center", fontsize=6.5)
    axis.set_xticks(range(matrix.shape[1]), labels=[f"{value:g}" for value in matrix.columns])
    axis.set_yticks(range(matrix.shape[0]), labels=[f"{value:g}" for value in matrix.index])
    axis.set_xlabel(r"$q_{route}$")
    axis.set_ylabel(r"$\sigma_{proxy}$")
    figure.colorbar(image, ax=axis, label="Population defect")
    _save(figure, run_dir, APPENDIX_FIGURE_IDS[0], primary, source, "Module A population-defect grid.")


def _contrast_forest(run_dir: Path, contrasts: pd.DataFrame, source: Path) -> None:
    data = contrasts[contrasts["contrast_family"] == "route_label_rate"].copy()
    figure, axis = plt.subplots(figsize=(6.2, 4.0))
    y = np.arange(len(data))
    axis.errorbar(data["paired_mean_difference"], y, xerr=1.96 * data["paired_mcse"], fmt="o", color="#2F6B9A", capsize=2)
    axis.axvline(0.0, color="0.4", linestyle="--", linewidth=0.8)
    axis.set_yticks(y, labels=data["contrast_id"])
    axis.set_xlabel("Paired mean difference")
    _save(figure, run_dir, APPENDIX_FIGURE_IDS[1], data, source, "Shared-seed route-label contrasts.")


def _optimal_set_conflict(run_dir: Path, population: pd.DataFrame, source: Path) -> None:
    data = population[population["route_id"] == "proxy_label"]
    figure, axis = plt.subplots(figsize=(5.2, 3.0))
    for sigma in MODULE_A.proxy_noise_sds:
        group = data[np.isclose(data["attribution_proxy_noise_sd"], sigma)].sort_values("route_label_rate")
        axis.plot(group["route_label_rate"], group["route_optimal_set_conflict_rate_mean"], marker="o", color=NOISE_COLORS[sigma], label=f"sigma={sigma:g}")
    axis.set_xlabel(r"$q_{route}$")
    axis.set_ylabel("Optimal-set conflict rate")
    axis.legend(frameon=False, ncol=2)
    axis.grid(axis="y")
    _save(figure, run_dir, APPENDIX_FIGURE_IDS[2], data, source, "Optimal-set conflict, distinct from pairwise sign disagreement.")


def _ambiguity_relation(run_dir: Path, selection: pd.DataFrame, source: Path) -> None:
    data = selection[selection["audit_design_id"] == "ambiguity_decile_population"]
    figure, axis = plt.subplots(figsize=(4.8, 3.0))
    axis.plot(data["mean_ambiguity"], data["mean_true_unit_defect"], marker="o", color="#C75B39")
    axis.set_xlabel("Mean ambiguity")
    axis.set_ylabel("Mean true unit defect")
    axis.grid()
    _save(figure, run_dir, APPENDIX_FIGURE_IDS[3], data, source, "Ambiguity-decile relation to true unit defect.")


def _weight_figures(run_dir: Path, weights: pd.DataFrame, source: Path) -> None:
    data = weights[weights["audit_design_id"] == "ambiguity_selective_ipw"]
    figure, axis = plt.subplots(figsize=(4.8, 3.0))
    axis.plot(data["audit_evidence_rate"], data["mean_weight_p95"], marker="o", label="p95 weight")
    axis.plot(data["audit_evidence_rate"], data["mean_weight_max"], marker="s", label="maximum weight")
    axis.set_xlabel(r"$\rho_{audit}$")
    axis.set_ylabel("IPW weight")
    axis.legend(frameon=False)
    axis.grid(axis="y")
    _save(figure, run_dir, APPENDIX_FIGURE_IDS[4], data, source, "IPW weight diagnostics and positivity support.")
    figure, axis = plt.subplots(figsize=(5.2, 3.0))
    axis.plot(data["audit_evidence_rate"], data["mean_labelled_sample_size"], marker="o", label=r"$n_{lab}$")
    axis.plot(data["audit_evidence_rate"], data["mean_effective_sample_size"], marker="s", label=r"$n_{eff}$")
    axis.set_xlabel(r"$\rho_{audit}$")
    axis.set_ylabel("Mean support")
    axis.legend(frameon=False)
    axis.grid(axis="y")
    _save(figure, run_dir, APPENDIX_FIGURE_IDS[5], data, source, "Labelled and effective support for selective IPW.")


def _parameter_recovery(run_dir: Path, parameters: pd.DataFrame, source: Path) -> None:
    data = parameters[parameters["control_id"] == "affine_linked"]
    figure, axis = plt.subplots(figsize=(4.8, 3.0))
    x = np.arange(len(data))
    axis.bar(x, data["mean_estimate"], color=("#2F6B9A", "#B07A1B"))
    axis.scatter(x, data["true_value"], color="black", marker="D", label="True value")
    axis.set_xticks(x, labels=data["parameter"])
    axis.set_ylabel("Parameter value")
    axis.legend(frameon=False)
    _save(figure, run_dir, APPENDIX_FIGURE_IDS[6], data, source, "Affine-control intercept and slope recovery.")


def _correspondence(run_dir: Path, checks: pd.DataFrame, source: Path) -> None:
    data = checks[checks["control_id"] == "blocked_correspondence_destroyed"]
    figure, axis = plt.subplots(figsize=(4.8, 3.0))
    values = [float(data["pre_mean_abs_pearson"].iloc[0]), float(data["post_mean_abs_pearson"].iloc[0])]
    axis.bar((0, 1), values, color=("#2F6B9A", "#C75B39"))
    axis.set_xticks((0, 1), labels=("Before", "After"))
    axis.set_ylabel("Mean absolute Pearson correlation")
    _save(figure, run_dir, APPENDIX_FIGURE_IDS[7], data, source, "Correspondence before and after blocked permutation.")


def _attribution(run_dir: Path, seed_level: pd.DataFrame, source: Path) -> None:
    rows = seed_level[(seed_level["route_id"] == "proxy_label") & np.isclose(seed_level["attribution_proxy_noise_sd"], MODULE_A.primary_proxy_noise_sd)]
    data = rows.groupby("route_label_rate", sort=True).agg(
        mean_entropy=("mean_attribution_entropy", "mean"),
        mean_max_mass=("mean_max_assignment_mass", "mean"),
        mean_true_source_mass=("mean_true_source_assigned_mass_appendix", "mean"),
    ).reset_index()
    figure, axis = plt.subplots(figsize=(5.0, 3.0))
    for column, label, marker in (("mean_entropy", "Entropy", "o"), ("mean_max_mass", "Maximum mass", "s"), ("mean_true_source_mass", "True-source mass", "^")):
        axis.plot(data["route_label_rate"], data[column], marker=marker, label=label)
    axis.set_xlabel(r"$q_{route}$")
    axis.set_ylabel("Attribution diagnostic")
    axis.legend(frameon=False)
    axis.grid(axis="y")
    _save(figure, run_dir, APPENDIX_FIGURE_IDS[8], data, source, "Attribution diagnostics remain appendix-only.")


def _robustness(run_dir: Path, population: pd.DataFrame, source: Path) -> None:
    smooth = population[population["route_id"] == "proxy_label_smooth_robustness"].sort_values("route_label_rate")
    primary = population[(population["route_id"] == "proxy_label") & np.isclose(population["attribution_proxy_noise_sd"], MODULE_A.primary_proxy_noise_sd)].sort_values("route_label_rate")
    data = pd.concat((primary.assign(dgp="Primary parity-floor DGP"), smooth.assign(dgp="Smooth no-parity-floor DGP")), ignore_index=True)
    figure, axis = plt.subplots(figsize=(5.0, 3.0))
    for label, group in data.groupby("dgp", sort=False):
        axis.plot(group["route_label_rate"], group["population_action_gap_defect_mean"], marker="o", label=label)
    axis.set_xlabel(r"$q_{route}$")
    axis.set_ylabel("Population action-gap defect")
    axis.legend(frameon=False)
    axis.grid(axis="y")
    _save(figure, run_dir, APPENDIX_FIGURE_IDS[9], data, source, "Smooth-loss robustness without parity-dependent floors.")


def plot_appendix_figures(run_dir: Path) -> None:
    set_publication_style()
    module_a = run_dir / "derived" / "module_a"
    module_b = run_dir / "derived" / "module_b"
    module_c = run_dir / "derived" / "module_c"
    paths = {
        "population": module_a / "exp4_module_a_population_summary.csv",
        "contrasts": module_a / "exp4_module_a_paired_contrasts.csv",
        "seed": module_a / "exp4_module_a_seed_level.parquet",
        "selection": module_b / "exp4_module_b_selection_diagnostics.csv",
        "weights": module_b / "exp4_module_b_weight_diagnostics.csv",
        "parameters": module_c / "exp4_module_c_parameter_recovery.csv",
        "correspondence": module_c / "exp4_module_c_correspondence_checks.csv",
    }
    data = {
        key: pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
        for key, path in paths.items()
    }
    _heatmap(run_dir, data["population"], paths["population"])
    _contrast_forest(run_dir, data["contrasts"], paths["contrasts"])
    _optimal_set_conflict(run_dir, data["population"], paths["population"])
    _ambiguity_relation(run_dir, data["selection"], paths["selection"])
    _weight_figures(run_dir, data["weights"], paths["weights"])
    _parameter_recovery(run_dir, data["parameters"], paths["parameters"])
    _correspondence(run_dir, data["correspondence"], paths["correspondence"])
    _attribution(run_dir, data["seed"], paths["seed"])
    _robustness(run_dir, data["population"], paths["population"])

from __future__ import annotations

"""Generate appendix mechanism-audit figures from frozen derived data only."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import DISPLAY_NAMES
from src.artifact_io import (
    atomic_write_json,
    hash_payload,
    refresh_output_manifest,
    sha256_file,
    utc_now,
)

PROJECT_ROOT = Path(__file__).resolve().parent


def _scientific_source_lineage() -> str:
    """Scientific lineage recorded when calibration was frozen."""
    manifest_path = PROJECT_ROOT / "calibration" / "exp1_calibration_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return manifest.get("code_lineage", "unavailable")


def _presentation_source_lineage() -> str:
    """Fingerprint of the presentation-only figure source in this package."""
    import hashlib

    h = hashlib.sha256()
    for name in ("plot_main.py", "plot_appendix.py"):
        file_path = PROJECT_ROOT / name
        h.update(name.encode("utf-8"))
        h.update(file_path.read_bytes())
    return "presentation:" + h.hexdigest()


def _require_files(paths: list[Path], run_tier: str) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise RuntimeError(
            "Missing frozen appendix-figure data: " + ", ".join(missing) + ". "
            f"Run `python main.py {run_tier}`, `python self_check.py --run {run_tier}`, "
            f"and `python targeted.py --run {run_tier}` first."
        )


def generate_delay_verification(output: Path) -> tuple[Path, Path]:
    survival_path = output / "figures" / "data" / "fig_exp1_delay_survival_data.csv"
    coupling_path = output / "figures" / "data" / "fig_exp1_state_coupling_data.csv"
    _require_files([survival_path, coupling_path], output.name)
    survival = pd.read_csv(survival_path)
    coupling = pd.read_csv(coupling_path)
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.3), constrained_layout=True)
    ax = axes[0]
    for mechanism in ("geometric_delay", "mixture_delay", "state_coupled_delay"):
        group = survival[survival.mechanism_id == mechanism]
        ax.plot(
            group.delay_threshold,
            group.estimate,
            label=group.mechanism_display_name.iloc[0],
        )
    ax.set_xlabel(r"Delay threshold $d$")
    ax.set_ylabel(r"$\Pr(\tau>d)$")
    ax.set_ylim(0, 1)
    ax.set_title("(a) Matched-mean delay survival")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)

    ax = axes[1]
    ax.errorbar(
        coupling.mean_state,
        coupling.estimate,
        yerr=[
            coupling.estimate - coupling.ci_lower,
            coupling.ci_upper - coupling.estimate,
        ],
        fmt="o-",
        capsize=3,
    )
    ax.set_xlabel("Mean structural state within decile")
    ax.set_ylabel("Mean generated delay")
    ax.set_title("(b) State-coupled delay verification")
    ax.grid(alpha=0.25)

    png = output / "figures" / "png" / "fig_exp1_delay_verification.png"
    pdf = output / "figures" / "pdf" / "fig_exp1_delay_verification.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    return png, pdf


def generate_margin_reversal(output: Path) -> tuple[Path, Path]:
    data_path = output / "figures" / "data" / "fig_exp1_reversal_margin_data.csv"
    _require_files([data_path], output.name)
    data = pd.read_csv(data_path)
    fig, axes = plt.subplots(1, 3, figsize=(13.4, 4.3), constrained_layout=True)

    summary = data[data.panel_id == "A"].copy()
    order = [
        "affected_round_fraction",
        "q10_reversal_margin",
        "near_zero_reversal_margin_share",
    ]
    labels = [
        "Affected-round fraction",
        "Q10 conflict margin",
        "Near-zero conflict-margin share",
    ]
    values = [
        float(summary.loc[summary.metric_id == metric, "estimate"].iloc[0])
        for metric in order
    ]
    lower = [
        float(summary.loc[summary.metric_id == metric, "ci_lower"].iloc[0])
        for metric in order
    ]
    upper = [
        float(summary.loc[summary.metric_id == metric, "ci_upper"].iloc[0])
        for metric in order
    ]
    x = np.arange(len(order))
    axes[0].errorbar(
        x,
        values,
        yerr=[np.array(values) - np.array(lower), np.array(upper) - np.array(values)],
        fmt="o",
        capsize=3,
    )
    axes[0].set_xticks(x, labels, rotation=18, ha="right")
    axes[0].set_title("(a) Persistent-conflict gates")
    axes[0].grid(axis="y", alpha=0.25)

    distribution = data[data.panel_id == "B"].sort_values("quantile")
    axes[1].plot(
        distribution["quantile"], distribution.estimate, marker="o", markersize=3
    )
    axes[1].fill_between(
        distribution["quantile"],
        distribution.ci_lower,
        distribution.ci_upper,
        alpha=0.18,
    )
    axes[1].axhline(0.20, linestyle="--", linewidth=1.0, alpha=0.7)
    axes[1].set_xlabel("Quantile")
    axes[1].set_ylabel("Conflict margin")
    axes[1].set_title("(b) Margin-separated conflicts")
    axes[1].grid(alpha=0.25)

    boundary = data[data.panel_id == "C"].sort_values("t")
    axes[2].step(
        boundary.t,
        boundary.structural_best_action,
        where="post",
        label="Structural best",
    )
    axes[2].step(
        boundary.t, boundary.route_best_action, where="post", label="Arrival-route best"
    )
    axes[2].fill_between(
        boundary.t,
        boundary.structural_best_action,
        boundary.route_best_action,
        where=boundary.ranking_reversal.astype(bool),
        alpha=0.18,
        step="post",
    )
    axes[2].axvline(
        float(boundary.boundary_center.iloc[0]),
        linestyle="--",
        linewidth=1.0,
        alpha=0.6,
    )
    axes[2].set_xlabel("Evaluation round")
    axes[2].set_ylabel("Action index")
    axes[2].set_title("(c) Representative block boundary")
    axes[2].grid(alpha=0.25)
    axes[2].legend(frameon=False, fontsize=8)

    png = output / "figures" / "png" / "fig_exp1_reversal_margin.png"
    pdf = output / "figures" / "pdf" / "fig_exp1_reversal_margin.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    return png, pdf


def generate_trajectory(output: Path) -> tuple[Path, Path]:
    data_path = output / "figures" / "data" / "fig_exp1_route_trajectory_data.csv"
    _require_files([data_path], output.name)
    data = pd.read_csv(data_path)
    fig, axes = plt.subplots(
        2, 1, figsize=(10.5, 5.8), sharex=True, constrained_layout=True
    )
    for ax, mechanism in zip(
        axes, ("exact_valid_shift", "systematic_misbinding"), strict=True
    ):
        group = data[data.mechanism_id == mechanism]
        ax.step(
            group.t,
            group.structural_best_action,
            where="post",
            label="Structural best action",
        )
        ax.step(
            group.t,
            group.route_best_action,
            where="post",
            label="Arrival-route best action",
        )
        ax.fill_between(
            group.t,
            group.structural_best_action,
            group.route_best_action,
            where=group.ranking_reversal.astype(bool),
            alpha=0.18,
            step="post",
        )
        ax.set_ylabel("Action index")
        ax.set_title(DISPLAY_NAMES[mechanism])
        ax.grid(alpha=0.2)
    axes[0].legend(frameon=False, ncol=2)
    axes[-1].set_xlabel("Evaluation round")
    png = output / "figures" / "png" / "fig_exp1_route_trajectory.png"
    pdf = output / "figures" / "pdf" / "fig_exp1_route_trajectory.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    return png, pdf


def generate_targeted_validation(output: Path) -> tuple[Path, Path] | tuple[()]:
    data_path = output / "targeted" / "fig_exp1_targeted_validation_data.csv"
    _require_files([data_path], output.name)
    data = pd.read_csv(data_path)
    mean_data = data[data.targeted_component == "mean_delay_robustness"].copy()
    horizon_data = data[
        (data.targeted_component == "horizon_scaling")
        & (data.metric_id == "structural_regret")
    ].copy()
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.3), constrained_layout=True)
    labels = {
        "arrival_clock": "Arrival-clock binding",
        "source_round": "Source-round binding",
    }
    for binding in ("arrival_clock", "source_round"):
        group = mean_data[mean_data.feedback_binding_id == binding].sort_values(
            "target_mean_delay"
        )
        axes[0].errorbar(
            group.target_mean_delay,
            group.estimate,
            yerr=[group.estimate - group.ci_lower, group.ci_upper - group.estimate],
            fmt="o-",
            capsize=3,
            label=labels[binding],
        )
    axes[0].set_xlabel("Target mean delay")
    axes[0].set_ylabel(r"Structural regret $R_T^c/T$")
    axes[0].set_title("(a) Mean-delay robustness")
    axes[0].grid(alpha=0.25)
    axes[0].legend(frameon=False)

    for binding in ("arrival_clock", "source_round"):
        group = horizon_data[horizon_data.feedback_binding_id == binding].sort_values(
            "target_horizon"
        )
        axes[1].errorbar(
            group.target_horizon,
            group.estimate,
            yerr=[group.estimate - group.ci_lower, group.ci_upper - group.estimate],
            fmt="o-",
            capsize=3,
            label=labels[binding],
        )
    axes[1].set_xlabel("Horizon $T$")
    axes[1].set_ylabel(r"Cumulative structural regret $R_T^c$")
    axes[1].set_title("(b) Systematic-misbinding horizon scaling")
    axes[1].grid(alpha=0.25)
    axes[1].legend(frameon=False)
    png = output / "figures" / "png" / "fig_exp1_targeted_validation.png"
    pdf = output / "figures" / "pdf" / "fig_exp1_targeted_validation.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    return png, pdf


FIGURE_ID_TARGETED_CANCELLATION = "fig_exp1_appendix_targeted_cancellation"
PANEL_A_RATIOS = (0.00, 1.00)
PROFILE_STYLES = {"static_shared": "-", "state_varying_shared": "--"}


def _errorbar(axis, x, frame, colour, linestyle, marker, label):
    if frame.empty:
        return
    axis.errorbar(
        x,
        frame.estimate,
        yerr=[frame.estimate - frame.ci_lower, frame.ci_upper - frame.estimate],
        fmt=marker,
        linestyle=linestyle,
        color=colour,
        capsize=3,
        label=label,
    )


def generate_targeted_cancellation_diagnostics(output: Path) -> tuple[Path, Path, Path]:
    """Appendix-candidate figure for the shared-vs-action-dependent cancellation.

    Route-map reporting only: every panel is built from the added targeted /
    derived reporting CSVs. The main Exp1 figure is never touched and nothing
    is marked ``paper_result``.
    """
    sweep_path = output / "targeted" / "exp1_targeted_cancellation_summary.csv"
    utilization_path = output / "derived" / "exp1_regret_stability_utilization_summary.csv"
    _require_files([sweep_path, utilization_path], output.name)
    sweep = pd.read_csv(sweep_path)
    utilization = pd.read_csv(utilization_path)

    fig, axes = plt.subplots(1, 3, figsize=(14.6, 4.6), constrained_layout=True)
    figure_rows: list[dict[str, object]] = []

    # (a) action-invariant level error grows with shared amplitude only.
    axis = axes[0]
    colours = {0.00: "#1f77b4", 1.00: "#d62728"}
    level_error = sweep[sweep.metric_id == "mean_absolute_actionwise_level_error"]
    for ratio in PANEL_A_RATIOS:
        for profile, linestyle in PROFILE_STYLES.items():
            subset = level_error[
                (level_error.alpha_dep == ratio) & (level_error.shared_profile == profile)
            ].sort_values("alpha_shared")
            _errorbar(
                axis,
                subset.alpha_shared,
                subset,
                colours[ratio],
                linestyle,
                "o",
                f"{profile} ($\\alpha_{{dep}}$={ratio:.2f})",
            )
            for row in subset.itertuples(index=False):
                figure_rows.append(
                    {
                        "figure_id": FIGURE_ID_TARGETED_CANCELLATION,
                        "panel_id": "A",
                        "shared_profile": profile,
                        "alpha_shared": float(row.alpha_shared),
                        "alpha_dep": float(row.alpha_dep),
                        "metric_id": "mean_absolute_actionwise_level_error",
                        "estimate": float(row.estimate),
                        "ci_lower": float(row.ci_lower),
                        "ci_upper": float(row.ci_upper),
                        "n_seeds": int(row.n_seeds),
                        "bootstrap_repetitions": int(row.bootstrap_repetitions),
                        "run_tier": output.name,
                        "paper_result": False,
                    }
                )
    axis.set_xlabel(r"Shared amplitude $\alpha_{\mathrm{shared}}$")
    axis.set_ylabel("Mean actionwise level error")
    axis.set_title("(a) Action-invariant level error")
    axis.grid(alpha=0.25)
    axis.legend(frameon=False, fontsize=8)

    # (b) decision metric vs residual ratio; shared amplitude is overlaid.
    axis = axes[1]
    chi = sweep[sweep.metric_id == "mean_chi"]
    scales = sorted(float(value) for value in chi.alpha_shared.unique())
    colour_map = plt.get_cmap("viridis")
    for index, scale in enumerate(scales):
        colour = colour_map(index / max(1, len(scales) - 1))
        subset = chi[
            (chi.shared_profile == "state_varying_shared") & (chi.alpha_shared == scale)
        ].sort_values("alpha_dep")
        _errorbar(axis, subset.alpha_dep, subset, colour, "-", "o", f"$\\alpha_{{shared}}$={scale:.2f}")
        static = chi[
            (chi.shared_profile == "static_shared") & (chi.alpha_shared == scale)
        ].sort_values("alpha_dep")
        axis.plot(
            static.alpha_dep,
            static.estimate,
            linestyle=":",
            marker="x",
            markersize=3.5,
            linewidth=1.0,
            color=colour,
        )
        for row in subset.itertuples(index=False):
            figure_rows.append(
                {
                    "figure_id": FIGURE_ID_TARGETED_CANCELLATION,
                    "panel_id": "B",
                    "shared_profile": "state_varying_shared",
                    "alpha_shared": float(row.alpha_shared),
                    "alpha_dep": float(row.alpha_dep),
                    "metric_id": "mean_chi",
                    "estimate": float(row.estimate),
                    "ci_lower": float(row.ci_lower),
                    "ci_upper": float(row.ci_upper),
                    "n_seeds": int(row.n_seeds),
                    "bootstrap_repetitions": int(row.bootstrap_repetitions),
                    "run_tier": output.name,
                    "paper_result": False,
                }
            )
    axis.plot([], [], linestyle=":", marker="x", color="0.4", label="static profile (C3)")
    axis.set_xlabel(r"Action-dependent ratio $\alpha_{\mathrm{dep}}$")
    axis.set_ylabel(r"Mean directed choice disagreement $\bar{\chi}$")
    axis.set_title("(b) Decision metric vs residual ratio")
    axis.set_ylim(-0.05, 1.05)
    axis.grid(alpha=0.25)
    axis.legend(frameon=False, fontsize=8, ncol=2)

    # (c) realized utilization of the sharp stability budget, arrival-assigned.
    axis = axes[2]
    arrival = utilization[utilization.route_id == "arrival_assigned"].reset_index(drop=True)
    if arrival.empty:
        raise RuntimeError("Missing arrival-assigned utilization summary rows")
    defined = arrival[arrival.n_defined.astype(int) > 0]
    for position, row in arrival.iterrows():
        if int(row.n_defined) > 0:
            axis.errorbar(
                position,
                float(row.estimate),
                yerr=[
                    [float(row.estimate) - float(row.ci_lower)],
                    [float(row.ci_upper) - float(row.estimate)],
                ],
                fmt="o",
                color="#1f77b4",
                capsize=3,
            )
            figure_rows.append(
                {
                    "figure_id": FIGURE_ID_TARGETED_CANCELLATION,
                    "panel_id": "C",
                    "shared_profile": "not_applicable",
                    "alpha_shared": float("nan"),
                    "alpha_dep": float("nan"),
                    "metric_id": "regret_stability_utilization",
                    "mechanism_id": row.mechanism_id,
                    "estimate": float(row.estimate),
                    "ci_lower": float(row.ci_lower),
                    "ci_upper": float(row.ci_upper),
                    "n_seeds": int(row.n_seeds),
                    "n_defined": int(row.n_defined),
                    "bootstrap_repetitions": int(row.bootstrap_repetitions),
                    "run_tier": output.name,
                    "paper_result": False,
                }
            )
        else:
            axis.axvline(position, color="0.88", linewidth=1.0, zorder=0)
            axis.annotate(
                "undefined\n(alignment\nbudget $\\equiv$ 0)",
                xy=(position, 0.02),
                xycoords=("data", "axes fraction"),
                ha="center",
                va="bottom",
                fontsize=7,
                color="0.4",
            )
    axis.set_xticks(list(range(len(arrival))))
    axis.set_xticklabels(
        [DISPLAY_NAMES[mechanism] for mechanism in arrival.mechanism_id],
        rotation=25,
        ha="right",
        fontsize=8,
    )
    axis.set_ylabel("Realized stability utilization")
    axis.set_title("(c) Realized stability-budget utilization")
    axis.set_ylim(0.0, float(max(0.35, defined.estimate.max() * 1.45)))
    axis.grid(alpha=0.25)
    axis.annotate(
        "undefined cells are never drawn as zero",
        xy=(0.5, 0.985),
        xycoords="axes fraction",
        ha="center",
        va="top",
        fontsize=7,
        color="0.4",
    )

    png = output / "figures" / "png" / f"{FIGURE_ID_TARGETED_CANCELLATION}.png"
    pdf = output / "figures" / "pdf" / f"{FIGURE_ID_TARGETED_CANCELLATION}.pdf"
    data_path = output / "figures" / "data" / f"{FIGURE_ID_TARGETED_CANCELLATION}_data.csv"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    figure_data = pd.DataFrame(figure_rows)
    figure_data.to_csv(data_path, index=False)
    atomic_write_json(
        output / "figures" / "metadata" / f"{FIGURE_ID_TARGETED_CANCELLATION}_metadata.json",
        {
            "figure_id": FIGURE_ID_TARGETED_CANCELLATION,
            "run_tier": output.name,
            "paper_result": False,
            "appendix_candidate": True,
            "main_figure_touched": False,
            "source_targeted_files": [str(sweep_path)],
            "source_derived_files": [str(utilization_path)],
            "source_data_sha256": sha256_file(data_path),
            "panel_definitions": {
                "A": "mean actionwise level error vs shared amplitude, separated by shared profile, for selected alpha_dep values",
                "B": "mean directed choice disagreement vs action-dependent ratio with shared-amplitude traces overlaid",
                "C": "realized stability-budget utilization for primary arrival-assigned mechanisms where defined",
            },
            "axis_definitions": {
                "A": "alpha_shared",
                "B": "alpha_dep",
                "C": "mechanism_id",
            },
            "uncertainty_definition": (
                "seed bootstrap over the targeted grid cells; undefined "
                "zero-budget cells are omitted, never drawn as zero"
            ),
            "cancellation_sweep_id": "cancellation_shared_vs_action_dependent",
            "generated_at": utc_now(),
            "figure_code_hash": sha256_file(PROJECT_ROOT / "plot_appendix.py"),
        },
    )
    return png, pdf, data_path


def generate_all(run_tier: str) -> list[Path]:
    """Render every appendix figure and its shared provenance metadata."""
    output = PROJECT_ROOT / "outputs" / run_tier
    artifacts = []
    for function in (
        generate_delay_verification,
        generate_margin_reversal,
        generate_trajectory,
        generate_targeted_validation,
        generate_targeted_cancellation_diagnostics,
    ):
        artifacts.extend(function(output))
    scientific_manifest = json.loads(
        (PROJECT_ROOT / "calibration" / "exp1_calibration_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    metadata = {
        "run_tier": run_tier,
        "paper_result": False,
        "generated_at": utc_now(),
        "scientific_source_lineage": _scientific_source_lineage(),
        "presentation_source_lineage": _presentation_source_lineage(),
        "scientific_artifact_manifest_hash": hash_payload(scientific_manifest),
        "figure_code_hash": sha256_file(PROJECT_ROOT / "plot_appendix.py"),
        "artifacts": [
            {
                "path": str(path.relative_to(output)),
                "sha256": sha256_file(path),
            }
            for path in artifacts
        ],
        "targeted_validation_status": (
            "PASS"
            if (output / "targeted" / "exp1_targeted_validation_report.json").exists()
            else "NOT_RUN"
        ),
    }
    atomic_write_json(
        output / "figures" / "metadata" / "exp1_appendix_figures_metadata.json",
        metadata,
    )
    refresh_output_manifest(output)
    return artifacts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_tier", nargs="?", choices=("fast", "full"))
    parser.add_argument("--run", dest="run_option", choices=("fast", "full"))
    args = parser.parse_args()
    run_tier = args.run_option or args.run_tier
    if run_tier is None:
        parser.error("provide run tier positionally or with --run")
    artifacts = generate_all(run_tier)
    print("APPENDIX_FIGURES_COMPLETE")
    for path in artifacts:
        print(path)


if __name__ == "__main__":
    main()

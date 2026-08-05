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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_tier", nargs="?", choices=("fast", "full"))
    parser.add_argument("--run", dest="run_option", choices=("fast", "full"))
    args = parser.parse_args()
    run_tier = args.run_option or args.run_tier
    if run_tier is None:
        parser.error("provide run tier positionally or with --run")
    output = PROJECT_ROOT / "outputs" / run_tier
    artifacts = []
    for function in (
        generate_delay_verification,
        generate_margin_reversal,
        generate_trajectory,
        generate_targeted_validation,
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
    print("APPENDIX_FIGURES_COMPLETE")
    refresh_output_manifest(output)
    for path in artifacts:
        print(path)


if __name__ == "__main__":
    main()

"""Additional appendix figures sourced only from frozen Exp3 tables."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from figure_bundle import write_figure_bundle
from utilities import sha256_file


COLORS = {
    "arrival_carrier": "#B24A3A",
    "history_mean_control": "#4C72B0",
    "ridge_proxy": "#2A7F62",
}


def _write(
    figure: plt.Figure,
    data: pd.DataFrame,
    output_dir: Path,
    figure_id: str,
    sources: list[Path],
    provenance: dict[str, object],
    interpretation: str,
) -> None:
    for key, value in provenance.items():
        if key != "generated_at_utc":
            data[f"figure_{key}"] = value
    write_figure_bundle(
        figure,
        data,
        output_dir,
        figure_id,
        {
            **provenance,
            "source_derived_files": [p.relative_to(output_dir).as_posix() for p in sources],
            "source_file_hashes": {
                p.relative_to(output_dir).as_posix(): sha256_file(p) for p in sources
            },
            "interpretation": interpretation,
            "formal_ci_validated": False,
        },
        figure_section="appendix",
    )
    plt.close(figure)


def plot_score_calibration(output_dir: Path, provenance: dict[str, object]) -> None:
    source = output_dir / "tables" / "exp3_decile_calibration.csv"
    table = pd.read_csv(source)
    figure, ax = plt.subplots(figsize=(5.7, 4.2))
    for route_id, group in table.groupby("route_id", observed=True):
        group = group.sort_values("calibration_decile")
        ax.plot(
            group["mean_predicted_target"],
            group["mean_observed_target"],
            marker="o",
            color=COLORS.get(str(route_id), "0.35"),
            label=str(route_id),
        )
    values = np.r_[table["mean_predicted_target"], table["mean_observed_target"]]
    low, high = float(np.nanmin(values)), float(np.nanmax(values))
    ax.plot([low, high], [low, high], linestyle="--", color="0.45", linewidth=0.9)
    ax.set_xlabel("Mean route score")
    ax.set_ylabel("Mean constructed target")
    ax.set_title("Score calibration by frozen decile", loc="left", fontweight="semibold")
    ax.legend(frameon=False)
    ax.grid(alpha=0.18)
    _write(
        figure,
        table.copy(),
        output_dir,
        "exp3_appendix_score_calibration",
        [source],
        provenance,
        "Decile calibration diagnostic; not a separate primary estimand.",
    )


def plot_gap_error_distribution(output_dir: Path, provenance: dict[str, object]) -> None:
    source = output_dir / "tables" / "exp3_gap_error_distribution.csv"
    table = pd.read_csv(source)
    route_order = ["arrival_carrier", "history_mean_control", "ridge_proxy"]
    values = [
        table.loc[table["route_id"] == route, "absolute_reference_pair_gap_error"].dropna()
        for route in route_order
    ]
    figure, ax = plt.subplots(figsize=(6.2, 4.0))
    ax.boxplot(values, labels=route_order, showfliers=False)
    ax.set_ylabel("Absolute held-out reference-pair gap error")
    ax.set_title("Reference-pair gap error distribution", loc="left", fontweight="semibold")
    ax.grid(axis="y", alpha=0.18)
    _write(
        figure,
        table.copy(),
        output_dir,
        "exp3_appendix_gap_error_distribution",
        [source],
        provenance,
        "Pair-level distribution explains maximum, mean, and P90 gap-error summaries.",
    )


def plot_route_selection_concentration(output_dir: Path, provenance: dict[str, object]) -> None:
    source = output_dir / "diagnostics" / "exp3_route_selection_diagnostics.csv"
    table = pd.read_csv(source)
    figure, axes = plt.subplots(1, 2, figsize=(7.2, 3.5))
    y = np.arange(len(table))
    axes[0].barh(y, table["maximum_selected_action_share"], color="#4C72B0")
    axes[0].set_yticks(y, table["route_id"].astype(str))
    axes[0].invert_yaxis()
    axes[0].set_xlabel("Maximum selected-action share")
    axes[1].barh(y, table["selected_action_entropy"], color="#2A7F62")
    axes[1].set_yticks(y, [])
    axes[1].set_xlabel("Selected-action entropy")
    for ax in axes:
        ax.grid(axis="x", alpha=0.18)
    figure.suptitle("Route-selection concentration", x=0.08, ha="left", fontweight="semibold")
    _write(
        figure,
        table.copy(),
        output_dir,
        "exp3_appendix_route_selection_concentration",
        [source],
        provenance,
        "Selection concentration diagnostic; it does not estimate deployment performance.",
    )


def plot_additional_appendix_figures(output_dir: Path, provenance: dict[str, object]) -> None:
    plot_score_calibration(output_dir, provenance)
    plot_gap_error_distribution(output_dir, provenance)
    plot_route_selection_concentration(output_dir, provenance)

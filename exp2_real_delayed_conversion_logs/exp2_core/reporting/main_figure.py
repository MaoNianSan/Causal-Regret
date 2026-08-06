from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from contracts import PRIMARY_SOURCE_ROUTE_ORDER, route_display_label
from data_io import write_json

from .artifact_metadata import save_figure, sha256
from .source_data import build_main_figure_source
from .style import set_publication_style, shared_count


def make_main_figure(
    arrival_displacement: pd.DataFrame,
    source_pairwise: pd.DataFrame,
    output_dir: str | Path,
    config: dict[str, Any],
    *,
    run_metadata: dict[str, Any],
) -> dict[str, Any]:
    set_publication_style(config)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    route_order = list(PRIMARY_SOURCE_ROUTE_ORDER)
    arrival, pairwise, combined = build_main_figure_source(
        arrival_displacement, source_pairwise, run_id=run_metadata["run_id"]
    )
    figure_data_path = output_dir / "figure_exp2_attribution_sensitivity_source.csv"
    combined.to_csv(figure_data_path, index=False)

    plots = config["plots"]
    fig, axes = plt.subplots(
        2,
        3,
        figsize=(float(plots["main_figure_width_in"]), 6.0),
        gridspec_kw={"width_ratios": [1.0, 1.0, 0.58], "hspace": 0.52, "wspace": 0.38},
    )

    def plot_block(
        row_axes: np.ndarray,
        frame: pd.DataFrame,
        labels: list[str],
        *,
        panel_label: str,
        tv_column: str,
        kendall_column: str,
        overlap_column: str,
    ) -> None:
        y = np.arange(len(frame))[::-1]
        cap = 0.08
        metric_specs = (
            (row_axes[0], tv_column, "allocation_tv", (0.0, 1.0), "Allocation TV"),
            (row_axes[1], kendall_column, "kendall_tau_b", (-1.0, 1.0), "Kendall tau-b"),
        )
        for axis, point_column, summary_prefix, limits, label in metric_specs:
            lower = frame[f"{summary_prefix}_resampling_q025"].to_numpy(dtype=float)
            upper = frame[f"{summary_prefix}_resampling_q975"].to_numpy(dtype=float)
            point = frame[point_column].to_numpy(dtype=float)
            axis.hlines(y, lower, upper, linewidth=float(plots["line_width"]))
            axis.scatter(point, y, s=float(plots["marker_size"]) ** 2, zorder=3)
            axis.vlines(lower, y - cap, y + cap, linewidth=0.8)
            axis.vlines(upper, y - cap, y + cap, linewidth=0.8)
            axis.set_xlim(*limits)
            axis.set_xlabel(label)
            axis.grid(axis="x", alpha=0.25, linewidth=0.6)
        row_axes[0].set_yticks(y, labels)
        row_axes[1].set_yticks(y, [])
        row_axes[2].set_xlim(0.0, 1.0)
        row_axes[2].set_ylim(-0.5, len(frame) - 0.5)
        row_axes[2].set_yticks([])
        row_axes[2].set_xticks([])
        row_axes[2].set_xlabel(f"Top-{int(frame['top_k'].iloc[0])} shared")
        for y_value, row in zip(y, frame.itertuples(index=False), strict=True):
            point = getattr(row, overlap_column)
            lower = row.top_k_overlap_resampling_q025
            upper = row.top_k_overlap_resampling_q975
            top_k = int(row.top_k)
            row_axes[2].text(
                0.5,
                y_value,
                f"{shared_count(point, top_k)}/{top_k} [{shared_count(lower, top_k)}, {shared_count(upper, top_k)}]",
                ha="center",
                va="center",
                fontsize=float(plots["annotation_font_size"]),
            )
        row_axes[2].spines[["top", "right", "bottom", "left"]].set_visible(False)
        row_axes[0].text(
            -0.38,
            1.08,
            panel_label,
            transform=row_axes[0].transAxes,
            fontsize=float(plots["panel_label_font_size"]),
            fontweight="bold",
        )

    plot_block(
        axes[0],
        arrival,
        [route_display_label(route) for route in route_order],
        panel_label="(a)",
        tv_column="allocation_tv_vs_arrival",
        kendall_column="kendall_tau_b_vs_arrival",
        overlap_column="top_k_overlap_vs_arrival",
    )
    plot_block(
        axes[1],
        pairwise,
        pairwise["pair_label"].tolist(),
        panel_label="(b)",
        tv_column="allocation_tv",
        kendall_column="kendall_tau_b",
        overlap_column="top_k_overlap",
    )

    base = output_dir / "figure_exp2_attribution_sensitivity"
    files = save_figure(fig, base, config)
    plt.close(fig)
    metadata = {
        **run_metadata,
        "figure_id": "figure_exp2_attribution_sensitivity",
        "panel_definitions": {
            "a": "Source-time routes versus the arrival-time accounting anchor.",
            "b": "Pairwise source-time route comparisons.",
        },
        "axis_definitions": {
            "columns": ["allocation_tv", "kendall_tau_b", "top_k_overlap"],
            "rows": "fixed comparison order within each panel",
        },
        "uncertainty_definition": "Empirical 2.5%–97.5% UID-resampling range.",
        "source_data": str(figure_data_path.name),
        "source_data_sha256": sha256(figure_data_path),
        "figure_files": {path.name: sha256(path) for path in files},
    }
    metadata_path = output_dir / "figure_exp2_attribution_sensitivity_metadata.json"
    write_json(metadata, metadata_path)
    return {"figure_files": files, "source_data": figure_data_path, "metadata": metadata_path}

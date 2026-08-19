"""Exp2 presentation plotting helpers over the promoted frozen result source.

Pure presentation helpers extracted from ``presentation.py`` so that the
primary renderer module stays within the repository structure contract
(hard length limit). No scientific logic lives here: every helper reads
frozen columns from the promoted result source and only draws or maps them.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

from presentation.common import (
    PreviewLayout,
    assert_no_suptitle,
    standardize_long_form,
    write_figure_bundle,
)
from presentation.renderers import figure_metadata
from presentation_sources import PresentationSource

# Both renderer modules participate in the presentation code lineage.
_PRESENTATION_FILES = (
    Path(__file__).with_name("presentation.py"),
    Path(__file__),
)


def build_metadata(
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
    """Construct figure metadata over the presentation renderer modules."""
    return figure_metadata(
        source,
        claim=claim,
        panels=panels,
        metrics=metrics,
        boundary=boundary,
        code_paths=list(_PRESENTATION_FILES),
        contract=contract,
        sample_count=sample_count,
        uncertainty=uncertainty,
        marker_semantics=marker_semantics,
    )


def main_legend_handles() -> list[Line2D]:
    """Legend handles for the main 2x2 attribution-sensitivity figure."""
    return [
        Line2D(
            [0],
            [0],
            marker="o",
            color="#1f4e79",
            linestyle="none",
            label="Full-sample estimate",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            markerfacecolor="white",
            markeredgecolor="#1f4e79",
            color="#1f4e79",
            linestyle="none",
            label="UID-resampling median",
        ),
    ]


def draw_interval_panel(
    axis: plt.Axes,
    subset: pd.DataFrame,
    metric: str,
    y: np.ndarray,
    cap: float = 0.10,
) -> None:
    """Draw the interval-capped estimate markers for one main-figure panel."""
    point = subset[metric].to_numpy(float)
    median = subset[f"{metric}_resampling_q500"].to_numpy(float)
    low = subset[f"{metric}_resampling_q025"].to_numpy(float)
    high = subset[f"{metric}_resampling_q975"].to_numpy(float)
    axis.hlines(y, low, high, color="#1f4e79", linewidth=0.8)
    axis.vlines(low, y - cap, y + cap, color="#1f4e79", linewidth=0.7)
    axis.vlines(high, y - cap, y + cap, color="#1f4e79", linewidth=0.7)
    axis.plot(point, y, "o", color="#1f4e79", markersize=4)
    axis.plot(
        median,
        y,
        "o",
        markerfacecolor="white",
        markeredgecolor="#1f4e79",
        color="#1f4e79",
        markersize=4,
    )


def appendix_figure(
    source: PresentationSource,
    layout: PreviewLayout,
    *,
    figure_id: str,
    title: str,
    path: Path,
) -> None:
    """Draw one frozen Exp2 appendix diagnostic figure."""
    frame = pd.read_csv(path)
    fig, axis = plt.subplots(figsize=(7.1, 2.8), constrained_layout=True)
    long_rows: list[dict[str, Any]] = []
    if figure_id == "exp2_appendix_ambiguity_heatmap":
        plotted = frame[frame.record_type.eq("source_route_pair")].copy()
        matrix = plotted.pivot_table(
            index="ambiguity_stratum",
            columns="display_label",
            values="allocation_tv",
            aggfunc="first",
        )
        image = axis.imshow(matrix.to_numpy(float), aspect="auto", cmap="viridis")
        axis.set_xticks(
            np.arange(len(matrix.columns)), matrix.columns, rotation=30, ha="right"
        )
        axis.set_yticks(np.arange(len(matrix.index)), matrix.index)
        axis.set_xlabel("Source-time route pair")
        axis.set_ylabel("Ambiguity stratum")
        fig.colorbar(image, ax=axis, label="Allocation TV")
        metric_columns = ["allocation_tv"]
    elif figure_id == "exp2_appendix_delay_distribution":
        plotted = frame.copy()
        axis.bar(plotted.delay_bin, plotted.source_event_share, color="#1f4e79")
        axis.set_xlabel("Source-to-conversion delay")
        axis.set_ylabel("Source-event share")
        metric_columns = ["source_event_share"]
    else:
        plotted = frame[frame.metric.eq("top_k_overlap")].copy()
        matrix = plotted.pivot_table(
            index="route_left", columns="route_right", values="value", aggfunc="first"
        )
        image = axis.imshow(matrix.to_numpy(float), vmin=0, vmax=1, cmap="viridis")
        axis.set_xticks(
            np.arange(len(matrix.columns)), matrix.columns, rotation=30, ha="right"
        )
        axis.set_yticks(np.arange(len(matrix.index)), matrix.index)
        axis.set_xlabel("Right route")
        axis.set_ylabel("Left route")
        fig.colorbar(image, ax=axis, label="Top-k overlap")
        metric_columns = ["value"]
    for index, row in plotted.iterrows():
        for column in metric_columns:
            long_rows.append(
                {
                    "panel_id": "a",
                    "metric_id": (
                        "top_k_overlap"
                        if figure_id == "exp2_appendix_pairwise_topk"
                        else column
                    ),
                    "estimand_id": (
                        "top_k_overlap"
                        if figure_id == "exp2_appendix_pairwise_topk"
                        else column
                    ),
                    "condition_id": path.stem,
                    "series_id": column,
                    "point_estimate": row[column],
                    "uncertainty_role": "frozen appendix diagnostic",
                    "uncertainty_method": "source table",
                    "source_table": path.name,
                    "source_row_key": str(index),
                }
            )
    axis.set_title(title, loc="left", fontweight="bold")
    assert_no_suptitle(fig)
    long_frame = standardize_long_form(
        pd.DataFrame(long_rows),
        figure_id=figure_id,
        experiment_id=source.experiment_id,
        run_id=source.run_id,
        run_tier=source.run_tier,
        paper_result=source.paper_result,
        analysis_tier="appendix",
    )
    write_figure_bundle(
        fig,
        long_frame,
        layout,
        figure_id=figure_id,
        section="appendix",
        layout_profile="appendix",
        metadata=build_metadata(
            source,
            claim=title,
            panels={"a": title},
            metrics={column: column for column in metric_columns},
            boundary="Appendix diagnostic from frozen Exp2 outputs; no UID resampling recomputation.",
            contract={"layout": [1, 1], "source": path.name},
            uncertainty="Frozen result-table diagnostic",
        ),
        source_files=[path],
    )

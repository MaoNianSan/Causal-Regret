"""Exp2 presentation-only renderer over the promoted frozen result source."""

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
    configure_matplotlib,
    standardize_long_form,
    write_figure_bundle,
)
from presentation.renderers import (
    figure_metadata,
    write_manifest,
    write_standard_table,
    write_table_frame,
)
from presentation_sources import PresentationSource, load_run_manifest

MAIN_CONTRACT = {
    "layout": [2, 2],
    "canvas_inches": [7.1, 4.6],
    "source_vs_arrival_rows": 4,
    "source_pair_rows": 6,
    "metrics": ["allocation_tv", "kendall_tau_b"],
    "main_exclusions": ["top_k_overlap"],
}


def build_main_long_form(
    frame: pd.DataFrame, source: PresentationSource
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for index, row in frame.iterrows():
        group = (
            "source_vs_arrival"
            if row["record_type"] == "arrival_route"
            else "source_pair"
        )
        for metric in ("allocation_tv", "kendall_tau_b"):
            rows.append(
                {
                    "panel_id": group,
                    "metric_id": metric,
                    "estimand_id": metric,
                    "condition_id": row["display_label"],
                    "series_id": "full_sample_and_uid_median",
                    "point_estimate": row[metric],
                    "resampling_median": row[f"{metric}_resampling_q500"],
                    "interval_lower": row[f"{metric}_resampling_q025"],
                    "interval_upper": row[f"{metric}_resampling_q975"],
                    "uncertainty_role": "empirical 2.5%-97.5% UID-cluster resampling sensitivity range",
                    "uncertainty_method": "UID-cluster resampling; not a confidence interval",
                    "repetition_count": row.get("resampling_repetitions", 1000),
                    "sample_count": row.get("common_active_cell_count", pd.NA),
                    "unit": "unitless",
                    "better_direction": "metric-dependent",
                    "source_table": "figure_exp2_attribution_sensitivity_source.csv",
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


def _appendix_figure(
    source: PresentationSource,
    layout: PreviewLayout,
    *,
    figure_id: str,
    title: str,
    path: Path,
) -> None:
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
            panels={"a": title},
            metrics={column: column for column in metric_columns},
            boundary="Appendix diagnostic from frozen Exp2 outputs; no UID resampling recomputation.",
            contract={"layout": [1, 1], "source": path.name},
            uncertainty="Frozen result-table diagnostic",
        ),
        source_files=[path],
    )


def render_presentation(
    source: PresentationSource, preview_root: Path
) -> dict[str, Any]:
    configure_matplotlib()
    layout = PreviewLayout(preview_root, source.experiment_id, source.run_id)
    figure_source = (
        source.source_run / "figures/figure_exp2_attribution_sensitivity_source.csv"
    )
    frame = pd.read_csv(figure_source)
    frame["comparison_group"] = frame["record_type"].map(
        {"arrival_route": "source_vs_arrival", "source_route_pair": "source_pair"}
    )
    fig, axes = plt.subplots(2, 2, figsize=(7.1, 4.6), constrained_layout=True)
    specs = [
        (
            0,
            0,
            "source_vs_arrival",
            "allocation_tv",
            "Allocation TV",
            "(a) Source-time route vs arrival",
        ),
        (
            0,
            1,
            "source_vs_arrival",
            "kendall_tau_b",
            "Kendall tau-b",
            "(b) Source-time route vs arrival",
        ),
        (
            1,
            0,
            "source_pair",
            "allocation_tv",
            "Allocation TV",
            "(c) Pairwise source-time routes",
        ),
        (
            1,
            1,
            "source_pair",
            "kendall_tau_b",
            "Kendall tau-b",
            "(d) Pairwise source-time routes",
        ),
    ]
    for row_index, column_index, group, metric, xlabel, title in specs:
        axis = axes[row_index, column_index]
        subset = frame[frame.comparison_group.eq(group)].reset_index(drop=True)
        y = np.arange(len(subset))[::-1]
        point = subset[metric].to_numpy(float)
        median = subset[f"{metric}_resampling_q500"].to_numpy(float)
        low = subset[f"{metric}_resampling_q025"].to_numpy(float)
        high = subset[f"{metric}_resampling_q975"].to_numpy(float)
        cap = 0.10
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
        axis.set_yticks(y, subset["display_label"].tolist())
        axis.set_xlabel(xlabel)
        axis.set_title(title, loc="left", fontweight="bold")
        axis.grid(axis="x", alpha=0.22, linewidth=0.55)
        if metric == "kendall_tau_b":
            axis.axvline(0, color="0.55", linestyle="--", linewidth=0.7)
    fig.legend(
        handles=[
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
        ],
        frameon=False,
        loc="lower center",
        ncol=2,
        bbox_to_anchor=(0.5, -0.02),
    )
    assert_no_suptitle(fig)
    manifest = load_run_manifest(source)
    main = write_figure_bundle(
        fig,
        build_main_long_form(frame, source),
        layout,
        figure_id=source.main_figure_id,
        section="main",
        metadata=_metadata(
            source,
            claim="Attribution sensitivity on a fixed delayed-conversion cohort.",
            panels={
                "a": "Four source-time routes versus arrival accounting, Allocation TV.",
                "b": "Four source-time routes versus arrival accounting, Kendall tau-b.",
                "c": "Six source-route pairs, Allocation TV.",
                "d": "Six source-route pairs, Kendall tau-b.",
            },
            metrics={
                "allocation_tv": "Allocation TV",
                "kendall_tau_b": "Kendall tau-b",
            },
            boundary="Fixed-cohort attribution sensitivity; not causal attribution or policy value.",
            contract=MAIN_CONTRACT,
            sample_count=manifest.get("resampling_repetitions", 1000),
            uncertainty="Empirical 2.5%-97.5% UID-cluster resampling sensitivity range; not a confidence interval",
            marker_semantics={
                "filled_marker": "full-sample estimate",
                "open_marker": "UID-resampling median",
                "horizontal_range": "empirical UID-cluster sensitivity range",
            },
        ),
        source_files=[figure_source],
    )

    appendix_specs = [
        (
            "exp2_appendix_ambiguity_heatmap",
            "Ambiguity-mechanism diagnostics",
            source.source_run / "figures/figure_exp2_ambiguity_mechanism_source.csv",
        ),
        (
            "exp2_appendix_delay_distribution",
            "Delay-distribution diagnostics",
            source.source_run / "figures/figure_exp2_delay_appendix_data.csv",
        ),
        (
            "exp2_appendix_pairwise_topk",
            "Pairwise Top-k diagnostics",
            source.source_run / "figures/figure_exp2_pairwise_appendix_data.csv",
        ),
    ]
    for figure_id, title, path in appendix_specs:
        _appendix_figure(source, layout, figure_id=figure_id, title=title, path=path)

    for filename, stem, semantics in (
        (
            "table_exp2_cohort_flow.csv",
            "tab_exp2_cohort_flow",
            "Frozen cohort-flow table.",
        ),
        (
            "table_exp2_pairwise_appendix.csv",
            "tab_exp2_pairwise_appendix",
            "Complete pairwise and Top-k appendix table.",
        ),
        (
            "table_exp2_robustness_summary.csv",
            "tab_exp2_robustness",
            "Frozen 30-day, threshold, half-life, and k robustness table.",
        ),
    ):
        write_standard_table(
            layout,
            source.source_run / "tables" / filename,
            stem,
            semantics=semantics,
        )
    route_rows = frame[
        ["route_left", "route_right", "display_label", "record_type"]
    ].copy()
    write_table_frame(
        layout,
        route_rows,
        "tab_exp2_attribution_route_definitions",
        semantics="Frozen route and route-pair labels used by the main and appendix outputs.",
        source_files=[figure_source],
    )
    appendix_ids = [item[0] for item in appendix_specs]
    write_manifest(layout, source, figure_ids=[source.main_figure_id])
    write_manifest(layout, source, appendix=True, figure_ids=appendix_ids)
    return {"layout": layout, "main": main, "appendix_ids": appendix_ids}


__all__ = ["MAIN_CONTRACT", "build_main_long_form", "render_presentation"]

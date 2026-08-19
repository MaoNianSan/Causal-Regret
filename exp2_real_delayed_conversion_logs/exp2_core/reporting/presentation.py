"""Exp2 presentation-only renderer over the promoted frozen result source."""

from __future__ import annotations

import importlib.util
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
from presentation.renderers import (
    write_manifest,
    write_standard_table,
    write_table_frame,
)
from presentation_sources import PresentationSource, load_run_manifest


def _load_presentation_helpers() -> Any:
    """Load the sibling plotting helpers without polluting ``sys.path``.

    The presentation layer imports this renderer standalone; loading the
    helpers module by file (same pattern as the registry renderer loader)
    keeps the top-level ``presentation`` package from being shadowed by this
    module's own ``presentation.py`` name.
    """
    module_name = "_cr_exp_output_exp2_presentation_helpers"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    path = Path(__file__).resolve().parent / "presentation_helpers.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load Exp2 presentation helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_HELPERS = _load_presentation_helpers()
appendix_figure = _HELPERS.appendix_figure
build_metadata = _HELPERS.build_metadata
draw_interval_panel = _HELPERS.draw_interval_panel
main_legend_handles = _HELPERS.main_legend_handles


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
        paper_result=source.paper_result,
    )


def render_presentation(
    source: PresentationSource, preview_root: Path
) -> dict[str, Any]:
    configure_matplotlib()
    layout = PreviewLayout(
        preview_root, source.experiment_id, source.run_id, mode=source.mode
    )
    figure_source = (
        source.source_run / "figures/figure_exp2_attribution_sensitivity_source.csv"
    )
    frame = pd.read_csv(figure_source)
    frame["comparison_group"] = frame["record_type"].map(
        {"arrival_route": "source_vs_arrival", "source_route_pair": "source_pair"}
    )
    fig, axes = plt.subplots(2, 2, figsize=(7.1, 4.6), constrained_layout=False)
    # Explicit fixed margins (constrained_layout does not account for
    # figure-level legends): the bottom band reserves room for the legend
    # *inside* the canvas, below the bottom-row x labels.  ``left`` covers
    # the long attribution labels of the left column.
    fig.subplots_adjust(
        left=0.30, right=0.985, top=0.94, bottom=0.20, wspace=0.24, hspace=0.52
    )
    specs = [
        (
            0,
            0,
            "source_vs_arrival",
            "allocation_tv",
            "Allocation TV",
            "(a) Route vs arrival",
        ),
        (
            0,
            1,
            "source_vs_arrival",
            "kendall_tau_b",
            "Kendall tau-b",
            None,
        ),
        (
            1,
            0,
            "source_pair",
            "allocation_tv",
            "Allocation TV",
            "(b) Source-route pairs",
        ),
        (
            1,
            1,
            "source_pair",
            "kendall_tau_b",
            "Kendall tau-b",
            None,
        ),
    ]
    for row_index, column_index, group, metric, xlabel, title in specs:
        axis = axes[row_index, column_index]
        subset = frame[frame.comparison_group.eq(group)].reset_index(drop=True)
        y = np.arange(len(subset))[::-1]
        draw_interval_panel(axis, subset, metric, y)
        axis.set_yticks(
            y,
            subset["display_label"].tolist() if column_index == 0 else [],
        )
        axis.set_xlabel(xlabel)
        if title:
            # Row identity is a single short title on the left column; the
            # right column repeats the metric through its x label only.
            axis.set_title(title, loc="left", fontweight="bold")
        axis.grid(axis="x", alpha=0.22, linewidth=0.55)
        if metric == "kendall_tau_b":
            axis.axvline(0, color="0.55", linestyle="--", linewidth=0.7)
    # Legend sits inside the reserved bottom band: anchored at the canvas
    # bottom edge (never outside), clear of every bottom-row x label.
    fig.legend(
        handles=main_legend_handles(),
        frameon=False,
        loc="lower center",
        ncol=2,
        bbox_to_anchor=(0.5, 0.02),
    )
    assert_no_suptitle(fig)
    manifest = load_run_manifest(source)
    main = write_figure_bundle(
        fig,
        build_main_long_form(frame, source),
        layout,
        figure_id=source.main_figure_id,
        section="main",
        layout_profile="exp2_main",
        metadata=build_metadata(
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
        appendix_figure(source, layout, figure_id=figure_id, title=title, path=path)

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
            paper_result=source.paper_result,
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
        paper_result=source.paper_result,
    )
    appendix_ids = [item[0] for item in appendix_specs]
    write_manifest(layout, source, figure_ids=[source.main_figure_id])
    write_manifest(layout, source, appendix=True, figure_ids=appendix_ids)
    return {"layout": layout, "main": main, "appendix_ids": appendix_ids}


__all__ = ["MAIN_CONTRACT", "build_main_long_form", "render_presentation"]

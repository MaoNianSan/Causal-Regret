"""Exp3 presentation-only renderer over current paper-candidate tables."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
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
from presentation.renderers import figure_metadata, write_manifest, write_standard_table
from presentation_sources import PresentationSource, load_run_manifest

ROUTE_ORDER = ["arrival_carrier", "history_mean_control", "ridge_proxy"]
ROUTE_COLORS = {
    "arrival_carrier": "#b54708",
    "history_mean_control": "#1f4e79",
    "ridge_proxy": "#2e7d32",
}
ROUTE_MARKERS = {
    "arrival_carrier": "o",
    "history_mean_control": "s",
    "ridge_proxy": "D",
}
METRICS = [
    ("pooled_supported_cell_spearman", "Spearman", "panel_a_score"),
    ("pooled_supported_cell_mae", "MAE", "panel_a_score"),
    (
        "maximum_heldout_reference_pair_gap_error",
        "Max held-out gap error",
        "panel_b_gap",
    ),
    ("heldout_reference_pair_sign_agreement", "Sign agreement", "panel_b_gap"),
    (
        "top_action_agreement_with_fold_reference",
        "Top-action agreement",
        "panel_c_ranking",
    ),
    (
        "ridge_over_historical_paired_value_gain",
        "Paired value gain",
        "panel_c_ranking",
    ),
]
ROUTE_DISPLAY = ["Arrival carrier", "Historical mean", "Ridge proxy"]
MAIN_CONTRACT = {
    "layout": [2, 3],
    "canvas_inches": [7.1, 4.8],
    "metrics": [metric for metric, _, _ in METRICS],
    "routes": ROUTE_ORDER,
    "scope_paragraph_on_canvas": False,
    "uncertainty_role": "sensitivity range, not confidence interval",
}


def build_main_long_form(
    frame: pd.DataFrame, source: PresentationSource
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for index, row in frame[frame.metric_id.ne("support_scope")].iterrows():
        route_id = (
            row["route_id"]
            if pd.notna(row["route_id"])
            else row.get("contrast_id", "ridge_over_historical")
        )
        rows.append(
            {
                "panel_id": row["panel_id"],
                "metric_id": row["metric_id"],
                "estimand_id": row["metric_id"],
                "condition_id": route_id,
                "series_id": route_id,
                "point_estimate": row["full_sample_estimate"],
                "resampling_median": row["resampling_median"],
                "interval_lower": row["sensitivity_lower"],
                "interval_upper": row["sensitivity_upper"],
                "uncertainty_role": "empirical 2.5%-97.5% user-cluster resampling sensitivity range",
                "uncertainty_method": "user-cluster resampling; not a confidence interval",
                "repetition_count": 1000,
                "sample_count": pd.NA,
                "unit": "unitless",
                "better_direction": "metric-dependent",
                "source_table": "exp3_main_score_gap_ranking_data.csv",
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


def _appendix_composite(
    source: PresentationSource,
    layout: PreviewLayout,
    *,
    figure_id: str,
    title: str,
    paths: list[Path],
    panel_titles: list[str] | None = None,
) -> None:
    fig, axes = plt.subplots(
        1, len(paths), figsize=(7.1, 3.1), constrained_layout=True, squeeze=False
    )
    long_rows: list[dict[str, Any]] = []
    for panel_index, path in enumerate(paths):
        frame = pd.read_csv(path)
        axis = axes[0, panel_index]
        numeric = [
            column
            for column in frame.columns
            if pd.api.types.is_numeric_dtype(frame[column])
        ]
        for column in numeric[:3]:
            values = pd.to_numeric(frame[column], errors="coerce").dropna()
            axis.plot(values.index, values, marker=".", linewidth=0.7, label=column)
            for source_index, value in values.items():
                long_rows.append(
                    {
                        "panel_id": chr(ord("a") + panel_index),
                        "metric_id": column,
                        "estimand_id": column,
                        "condition_id": path.stem,
                        "series_id": column,
                        "point_estimate": value,
                        "uncertainty_role": "frozen appendix diagnostic",
                        "uncertainty_method": "source table",
                        "source_table": path.name,
                        "source_row_key": str(source_index),
                    }
                )
        if numeric:
            axis.legend(frameon=False, fontsize=6.5)
        # Short paper-facing panel titles; raw file stems are never exposed.
        if panel_titles is not None and panel_index < len(panel_titles):
            panel_title = panel_titles[panel_index]
        else:
            panel_title = path.stem.replace("exp3_", "").replace("_", " ").title()
        axis.set_title(panel_title, loc="left", fontweight="bold")
        axis.set_xlabel("Frozen source row")
        axis.grid(axis="y", alpha=0.2)
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
        metadata=_metadata(
            source,
            claim=title,
            panels={
                chr(ord("a") + index): path.stem for index, path in enumerate(paths)
            },
            metrics={},
            boundary="Appendix composite from frozen paper-candidate tables.",
            contract={
                "layout": [1, len(paths)],
                "sources": [path.name for path in paths],
            },
            uncertainty="Frozen diagnostic; sensitivity ranges are not confidence intervals",
        ),
        source_files=paths,
    )


def render_presentation(
    source: PresentationSource, preview_root: Path
) -> dict[str, Any]:
    configure_matplotlib()
    layout = PreviewLayout(
        preview_root, source.experiment_id, source.run_id, mode=source.mode
    )
    figure_source = (
        source.source_run / "figures/data/exp3_main_score_gap_ranking_data.csv"
    )
    table_source = source.source_run / "tables/exp3_primary_route_results.csv"
    frame = pd.read_csv(figure_source)
    fig, axes = plt.subplots(2, 3, figsize=(7.1, 4.8), constrained_layout=False)
    # Explicit fixed margins (mirrors the known-good experimental figure,
    # which also reserves a bottom band instead of relying on tight bbox):
    # the bottom band keeps the figure legend inside the canvas, below the
    # bottom-row x labels.
    fig.subplots_adjust(
        left=0.15, right=0.985, top=0.94, bottom=0.20, wspace=0.32, hspace=0.55
    )
    # Column-level conceptual meaning sits on the top row only; the row-level
    # metric identity is carried by each panel's x label, so no subplot
    # repeats a long sentence.
    column_titles = [
        "(a) Score recovery",
        "(b) Pair-gap recovery",
        "(c) Ranking recovery",
    ]
    for index, (metric, xlabel, _) in enumerate(METRICS):
        row_index, column_index = index % 2, index // 2
        axis = axes[row_index, column_index]
        subset = frame[frame.metric_id.eq(metric)]
        if metric == "ridge_over_historical_paired_value_gain":
            row = subset.iloc[0]
            axis.hlines(
                0,
                row.sensitivity_lower,
                row.sensitivity_upper,
                color="#2e7d32",
                linewidth=0.8,
            )
            axis.plot(
                row.full_sample_estimate,
                0,
                marker="D",
                color="#2e7d32",
                markerfacecolor="#2e7d32",
                markersize=4,
            )
            axis.plot(
                row.resampling_median,
                0,
                marker="D",
                color="#2e7d32",
                markerfacecolor="white",
                markersize=4,
            )
            axis.set_yticks([0], ["Ridge - Historical"])
            axis.axvline(0, color="0.55", linestyle="--", linewidth=0.7)
            span = max(
                row.sensitivity_upper - row.sensitivity_lower,
                abs(row.full_sample_estimate),
                abs(row.resampling_median),
                1e-6,
            )
            axis.set_xlim(
                min(
                    row.sensitivity_lower,
                    row.full_sample_estimate,
                    row.resampling_median,
                    0.0,
                )
                - 0.15 * span,
                max(
                    row.sensitivity_upper,
                    row.full_sample_estimate,
                    row.resampling_median,
                    0.0,
                )
                + 0.15 * span,
            )
        else:
            subset = subset.set_index("route_id").reindex(ROUTE_ORDER).reset_index()
            y = np.arange(len(subset))[::-1]
            values: list[float] = []
            for yi, row in zip(y, subset.itertuples(index=False), strict=True):
                color = ROUTE_COLORS[row.route_id]
                marker = ROUTE_MARKERS[row.route_id]
                axis.hlines(
                    yi,
                    row.sensitivity_lower,
                    row.sensitivity_upper,
                    color=color,
                    linewidth=0.8,
                )
                axis.plot(
                    row.full_sample_estimate,
                    yi,
                    marker=marker,
                    color=color,
                    markerfacecolor=color,
                    markersize=4,
                )
                axis.plot(
                    row.resampling_median,
                    yi,
                    marker=marker,
                    color=color,
                    markerfacecolor="white",
                    markersize=4,
                )
                values.extend(
                    [
                        row.full_sample_estimate,
                        row.resampling_median,
                        row.sensitivity_lower,
                        row.sensitivity_upper,
                    ]
                )
            # Route identity is shown once on the left column; the other
            # columns reuse the route shape/color semantics from the legend.
            axis.set_yticks(y, ROUTE_DISPLAY if column_index == 0 else [])
            if metric == "maximum_heldout_reference_pair_gap_error":
                axis.axvline(0, color="0.55", linestyle="--", linewidth=0.7)
                lower = min(0.0, min(values))
            else:
                lower = min(values)
            upper = max(values)
            span = max(upper - lower, 1e-6)
            axis.set_xlim(lower - 0.06 * span, upper + 0.10 * span)
        axis.set_xlabel(xlabel)
        if row_index == 0:
            axis.set_title(
                column_titles[column_index], loc="left", fontweight="bold"
            )
        axis.grid(axis="x", alpha=0.22, linewidth=0.55)
    fig.legend(
        handles=[
            Line2D(
                [0],
                [0],
                marker="o",
                color=ROUTE_COLORS["arrival_carrier"],
                linestyle="none",
                label="Arrival carrier",
            ),
            Line2D(
                [0],
                [0],
                marker="s",
                color=ROUTE_COLORS["history_mean_control"],
                linestyle="none",
                label="Historical mean",
            ),
            Line2D(
                [0],
                [0],
                marker="D",
                color=ROUTE_COLORS["ridge_proxy"],
                linestyle="none",
                label="Ridge proxy",
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="0.25",
                linestyle="none",
                label="Filled: full sample",
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                markerfacecolor="white",
                markeredgecolor="0.25",
                color="0.25",
                linestyle="none",
                label="Open: resampling median",
            ),
        ],
        frameon=False,
        loc="lower center",
        ncol=5,
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
        layout_profile="exp3_main",
        metadata=_metadata(
            source,
            claim="Logged-supported score, held-out pair-gap, and ranking recovery across three routes.",
            panels={
                "a": "Pooled supported-cell score recovery.",
                "b": "Held-out reference-pair gap recovery.",
                "c": "Logged-supported ranking recovery.",
            },
            metrics={metric: label for metric, label, _ in METRICS},
            boundary="Score recovery need not transfer to decision recovery; not OPE or causal regret.",
            contract=MAIN_CONTRACT,
            sample_count=manifest.get("bootstrap_repetitions", 1000),
            uncertainty="Empirical 2.5%-97.5% user-cluster resampling sensitivity range; not a confidence interval",
            marker_semantics={
                "filled_marker": "full-sample estimate",
                "open_marker": "user-cluster resampling median",
                "horizontal_range": "empirical user-cluster sensitivity range",
                "shape": "route identity",
            },
        ),
        source_files=[figure_source, table_source],
    )

    table_dir = source.source_run / "tables"
    figure_dir = source.source_run / "figures" / "data"
    appendix_groups = [
        (
            "exp3_appendix_support_and_dependence",
            "Support and dependence",
            [
                table_dir / "exp3_full_design_support_preflight.csv",
                table_dir / "exp3_data_dependence_structure.csv",
            ],
            ["Support preflight", "Dependence structure"],
        ),
        (
            "exp3_appendix_carrier_and_gap_diagnostics",
            "Carrier and gap diagnostics",
            [
                figure_dir / "exp3_appendix_arrival_carrier_diagnostic_data.csv",
                figure_dir / "exp3_appendix_gap_error_distribution_data.csv",
            ],
            ["Arrival-carrier diagnostic", "Gap-error distribution"],
        ),
        (
            "exp3_appendix_calibration_and_selection",
            "Calibration and selection",
            [
                table_dir / "exp3_decile_calibration.csv",
                figure_dir / "exp3_appendix_route_selection_concentration_data.csv",
            ],
            ["Decile calibration", "Route-selection concentration"],
        ),
    ]
    for figure_id, title, paths, panel_titles in appendix_groups:
        _appendix_composite(
            source,
            layout,
            figure_id=figure_id,
            title=title,
            paths=paths,
            panel_titles=panel_titles,
        )
    for filename in (
        "exp3_action_space_coverage.csv",
        "exp3_support_coverage.csv",
        "exp3_primary_route_results.csv",
        "exp3_paired_ranking_contrast.csv",
        "exp3_ridge_history_cv.csv",
        "exp3_ridge_coefficients.csv",
        "exp3_resampling_structure_diagnostics.csv",
    ):
        write_standard_table(
            layout,
            table_dir / filename,
            Path(filename).stem,
            semantics="Frozen Exp3 appendix table.",
            paper_result=source.paper_result,
        )
    appendix_ids = [item[0] for item in appendix_groups]
    write_manifest(layout, source, figure_ids=[source.main_figure_id])
    write_manifest(layout, source, appendix=True, figure_ids=appendix_ids)
    return {"layout": layout, "main": main, "appendix_ids": appendix_ids}


__all__ = ["MAIN_CONTRACT", "build_main_long_form", "render_presentation"]

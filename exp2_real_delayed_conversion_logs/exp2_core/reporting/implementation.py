from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

from contracts import PRIMARY_SOURCE_ROUTE_ORDER, SCHEMA_VERSION, route_display_label
from data_io import write_json


PAIR_LABELS = {
    ("first_click_or_touch", "last_click_or_touch"): "First–Last",
    ("first_click_or_touch", "linear_source_cell_credit"): "First–Linear",
    ("first_click_or_touch", "time_decay_source_cell_credit"): "First–Decay",
    ("last_click_or_touch", "linear_source_cell_credit"): "Last–Linear",
    ("last_click_or_touch", "time_decay_source_cell_credit"): "Last–Decay",
    ("linear_source_cell_credit", "time_decay_source_cell_credit"): "Linear–Decay",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _set_publication_style(config: dict[str, Any]) -> None:
    plots = config["plots"]
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": float(plots["tick_font_size"]),
            "axes.labelsize": float(plots["axis_label_font_size"]),
            "axes.titlesize": float(plots["axis_label_font_size"]),
            "xtick.labelsize": float(plots["tick_font_size"]),
            "ytick.labelsize": float(plots["tick_font_size"]),
            "legend.fontsize": float(plots["annotation_font_size"]),
            "axes.linewidth": 0.8,
            "lines.linewidth": float(plots["line_width"]),
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def _save_figure(fig: plt.Figure, base: Path, config: dict[str, Any]) -> list[Path]:
    plots = config["plots"]
    saved: list[Path] = []
    if bool(plots.get("save_pdf", True)):
        path = base.with_suffix(".pdf")
        fig.savefig(path, bbox_inches="tight")
        saved.append(path)
    if bool(plots.get("save_svg", True)):
        path = base.with_suffix(".svg")
        fig.savefig(path, bbox_inches="tight")
        saved.append(path)
    if bool(plots.get("save_png", True)):
        path = base.with_suffix(".png")
        fig.savefig(path, dpi=int(plots.get("dpi", 600)), bbox_inches="tight")
        saved.append(path)
    return saved


def _dynamic_tv_upper(values: pd.Series | np.ndarray, *, minimum: float = 0.15) -> float:
    numeric = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    maximum = float(numeric.max()) if not numeric.empty else 0.0
    return round(min(1.0, max(minimum, math.ceil(maximum / 0.05) * 0.05)), 2)


def _shared_count(value: float, top_k: int) -> int:
    return int(np.clip(np.rint(float(value) * int(top_k)), 0, int(top_k)))


def _shared_annotation(
    point: float, lower: float, upper: float, top_k: int, *, compact: bool = False
) -> str:
    prefix = "Shared" if compact else f"Top-{top_k} shared"
    return (
        f"{prefix}: {_shared_count(point, top_k)}/{top_k} "
        f"[{_shared_count(lower, top_k)}, {_shared_count(upper, top_k)}]"
    )


def make_main_figure(
    arrival_displacement: pd.DataFrame,
    source_pairwise: pd.DataFrame,
    output_dir: str | Path,
    config: dict[str, Any],
    *,
    run_metadata: dict[str, Any],
) -> dict[str, Any]:
    _set_publication_style(config)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    route_order = list(PRIMARY_SOURCE_ROUTE_ORDER)
    arrival = arrival_displacement.set_index("route_id").loc[route_order].reset_index()
    pairwise = source_pairwise.copy()
    pairwise["pair_label"] = [
        PAIR_LABELS.get((row.route_left, row.route_right), f"{row.route_left}–{row.route_right}")
        for row in pairwise.itertuples(index=False)
    ]

    source_columns = [
        "route_left",
        "route_right",
        "display_label",
        "allocation_tv",
        "allocation_tv_resampling_q025",
        "allocation_tv_resampling_q500",
        "allocation_tv_resampling_q975",
        "kendall_tau_b",
        "kendall_tau_b_resampling_q025",
        "kendall_tau_b_resampling_q500",
        "kendall_tau_b_resampling_q975",
        "top_k",
        "top_k_overlap",
        "top_k_overlap_resampling_q025",
        "top_k_overlap_resampling_q500",
        "top_k_overlap_resampling_q975",
        "common_active_cell_count",
    ]
    figure_data_arrival = arrival.assign(
        route_left="arrival_time_accounting_anchor",
        route_right=arrival["route_id"],
        display_label=arrival["route_id"].map(route_display_label),
        allocation_tv=arrival["allocation_tv_vs_arrival"],
        kendall_tau_b=arrival["kendall_tau_b_vs_arrival"],
        top_k_overlap=arrival["top_k_overlap_vs_arrival"],
    ).rename(
        columns={
            "route_id": "route_right_source",
        }
    )
    figure_data_arrival["panel"] = "a"
    figure_data_pairwise = pairwise.assign(display_label=pairwise["pair_label"], panel="b")
    figure_data_pairwise = figure_data_pairwise[source_columns]
    figure_data_arrival = figure_data_arrival[source_columns]

    combined = pd.concat(
        [
            figure_data_arrival.assign(record_type="arrival_route"),
            figure_data_pairwise.assign(record_type="source_route_pair"),
        ],
        ignore_index=True,
        sort=False,
    )
    combined["comparison_group"] = np.where(
        combined["record_type"].eq("arrival_route"),
        "source_vs_arrival_anchor",
        "source_route_pair",
    )
    combined["schema_version"] = SCHEMA_VERSION
    combined["run_id"] = run_metadata["run_id"]
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
                f"{_shared_count(point, top_k)}/{top_k} [{_shared_count(lower, top_k)}, {_shared_count(upper, top_k)}]",
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
    files = _save_figure(fig, base, config)
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
        "source_data_sha256": _sha256(figure_data_path),
        "figure_files": {path.name: _sha256(path) for path in files},
    }
    metadata_path = output_dir / "figure_exp2_attribution_sensitivity_metadata.json"
    write_json(metadata, metadata_path)
    return {"figure_files": files, "source_data": figure_data_path, "metadata": metadata_path}


def _pairwise_matrix(pairwise: pd.DataFrame, metric: str, diagonal: float | None) -> pd.DataFrame:
    routes = list(PRIMARY_SOURCE_ROUTE_ORDER)
    matrix = pd.DataFrame(np.nan, index=routes, columns=routes, dtype=float)
    if diagonal is not None:
        np.fill_diagonal(matrix.values, diagonal)
    for row in pairwise.itertuples(index=False):
        value = float(getattr(row, metric))
        matrix.loc[row.route_left, row.route_right] = value
        matrix.loc[row.route_right, row.route_left] = value
    return matrix


def make_pairwise_appendix_figure(
    source_pairwise: pd.DataFrame,
    output_dir: str | Path,
    config: dict[str, Any],
    *,
    run_metadata: dict[str, Any],
) -> dict[str, Any]:
    _set_publication_style(config)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tv_upper = _dynamic_tv_upper(source_pairwise["allocation_tv"])
    definitions: list[tuple[str, str, float, float, float, str, Any]] = [
        ("allocation_tv", "Allocation TV", 0.0, tv_upper, 0.0, "viridis", None),
        ("top_k_overlap", "Top-10 overlap", 0.0, 1.0, 1.0, "viridis", None),
        (
            "kendall_tau_b",
            "Kendall tau-b",
            -1.0,
            1.0,
            1.0,
            "coolwarm",
            TwoSlopeNorm(vmin=-1.0, vcenter=0.0, vmax=1.0),
        ),
    ]
    routes = list(PRIMARY_SOURCE_ROUTE_ORDER)
    display = ["First", "Last", "Linear", "Time-decay"]
    fig, axes = plt.subplots(
        1,
        3,
        figsize=(float(config["plots"].get("appendix_figure_width_in", 7.1)), 2.9),
        constrained_layout=True,
    )
    source_rows: list[dict[str, object]] = []
    upper_triangle_mask = np.tril(np.ones((len(routes), len(routes)), dtype=bool), k=0)
    for ax, (metric, title, vmin, vmax, diagonal, cmap, norm) in zip(
        axes, definitions, strict=True
    ):
        matrix = _pairwise_matrix(source_pairwise, metric, diagonal)
        shown = np.ma.array(matrix.to_numpy(dtype=float), mask=upper_triangle_mask)
        image_kwargs: dict[str, Any] = {"aspect": "equal", "cmap": cmap}
        if norm is None:
            image_kwargs.update({"vmin": vmin, "vmax": vmax})
        else:
            image_kwargs["norm"] = norm
        image = ax.imshow(shown, **image_kwargs)
        ax.set_title(title)
        ax.set_xticks(range(len(routes)), display, rotation=45, ha="right")
        ax.set_yticks(range(len(routes)), display)
        for i, left in enumerate(routes):
            for j, right in enumerate(routes):
                value = matrix.iloc[i, j]
                source_rows.append(
                    {
                        "metric": metric,
                        "route_left": left,
                        "route_right": right,
                        "value": value,
                    }
                )
                if j <= i:
                    continue
                label = "NA" if np.isnan(value) else f"{value:.2f}"
                ax.text(j, i, label, ha="center", va="center", fontsize=6.0)
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    source_path = output_dir / "figure_exp2_pairwise_appendix_data.csv"
    pd.DataFrame(source_rows).to_csv(source_path, index=False)
    base = output_dir / "figure_exp2_pairwise_appendix"
    files = _save_figure(fig, base, config)
    plt.close(fig)
    metadata = {
        **run_metadata,
        "figure_id": "figure_exp2_pairwise_appendix",
        "source_data": source_path.name,
        "source_data_sha256": _sha256(source_path),
        "figure_files": {path.name: _sha256(path) for path in files},
        "allocation_tv_color_limit": [0.0, tv_upper],
        "matrix_display": "Upper triangle only; the underlying pairwise metrics are symmetric.",
        "uncertainty_definition": "Point estimates shown; intervals are reported in the appendix table.",
    }
    metadata_path = output_dir / "figure_exp2_pairwise_appendix_metadata.json"
    write_json(metadata, metadata_path)
    return {"figure_files": files, "source_data": source_path, "metadata": metadata_path}


def make_ambiguity_figure(
    ambiguity: pd.DataFrame,
    output_dir: str | Path,
    config: dict[str, Any],
    *,
    run_metadata: dict[str, Any],
) -> dict[str, Any]:
    _set_publication_style(config)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    source = ambiguity.loc[ambiguity["record_type"].eq("source_route_pair")].copy()
    source["display_label"] = [
        PAIR_LABELS.get((row.route_left, row.route_right), f"{row.route_left}-{row.route_right}")
        for row in source.itertuples(index=False)
    ]
    source["schema_version"] = SCHEMA_VERSION
    source["run_id"] = run_metadata["run_id"]
    source_path = output_dir / "figure_exp2_ambiguity_mechanism_source.csv"
    source.to_csv(source_path, index=False)

    strata = ["candidate_cells_1", "candidate_cells_2", "candidate_cells_3plus"]
    pair_order = [PAIR_LABELS[pair] for pair in PAIR_LABELS]
    matrix = source.pivot_table(
        index="display_label",
        columns="candidate_cell_count_stratum",
        values="mean_journey_assignment_tv",
        aggfunc="first",
    ).reindex(index=pair_order, columns=strata)
    fig, ax = plt.subplots(figsize=(5.6, 3.4), constrained_layout=True)
    image = ax.imshow(matrix.to_numpy(dtype=float), vmin=0.0, vmax=1.0, cmap="viridis")
    ax.set_xticks(range(len(strata)), ["1 cell", "2 cells", "3+ cells"])
    ax.set_yticks(range(len(pair_order)), pair_order)
    for row_index in range(len(pair_order)):
        for column_index in range(len(strata)):
            value = matrix.iloc[row_index, column_index]
            ax.text(column_index, row_index, "NA" if pd.isna(value) else f"{value:.2f}", ha="center", va="center", fontsize=7)
    ax.set_xlabel("Candidate source cells per journey")
    ax.set_title("Mean journey assignment TV")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    base = output_dir / "figure_exp2_ambiguity_mechanism"
    files = _save_figure(fig, base, config)
    plt.close(fig)
    metadata = {
        **run_metadata,
        "figure_id": "figure_exp2_ambiguity_mechanism",
        "source_data": source_path.name,
        "source_data_sha256": _sha256(source_path),
        "figure_files": {path.name: _sha256(path) for path in files},
    }
    metadata_path = output_dir / "figure_exp2_ambiguity_mechanism_metadata.json"
    write_json(metadata, metadata_path)
    return {"figure_files": files, "source_data": source_path, "metadata": metadata_path}


def make_delay_composition_figure(
    candidates: pd.DataFrame,
    output_dir: str | Path,
    config: dict[str, Any],
    *,
    run_metadata: dict[str, Any],
) -> dict[str, Any]:
    _set_publication_style(config)
    output_dir = Path(output_dir)
    bins = [-np.inf, 1 / 24, 6 / 24, 1, 7, 30]
    labels = ["≤1 h", "1–6 h", "6–24 h", "1–7 d", "7–30 d"]
    categories = pd.cut(
        candidates["source_lag_days"], bins=bins, labels=labels, include_lowest=True, right=True
    )
    summary = categories.value_counts(sort=False).rename_axis("delay_bin").reset_index(name="source_event_count")
    summary["source_event_share"] = summary["source_event_count"] / summary["source_event_count"].sum()
    source_path = output_dir / "figure_exp2_delay_appendix_data.csv"
    summary.to_csv(source_path, index=False)

    fig, ax = plt.subplots(figsize=(4.9, 2.6))
    y = np.arange(len(summary))[::-1]
    ax.barh(y, summary["source_event_share"])
    ax.set_yticks(y, summary["delay_bin"])
    ax.set_xlim(0.0, max(1.0, float(summary["source_event_share"].max()) * 1.15))
    ax.set_xlabel("Share of eligible source events")
    for y_value, row in zip(y, summary.itertuples(index=False), strict=True):
        ax.text(
            row.source_event_share,
            y_value,
            f" {row.source_event_share:.1%} ({row.source_event_count:,})",
            va="center",
            fontsize=float(config["plots"]["annotation_font_size"]),
        )
    ax.grid(axis="x", alpha=0.25, linewidth=0.6)
    base = output_dir / "figure_exp2_delay_appendix"
    files = _save_figure(fig, base, config)
    plt.close(fig)
    metadata = {
        **run_metadata,
        "figure_id": "figure_exp2_delay_appendix",
        "source_data": source_path.name,
        "source_data_sha256": _sha256(source_path),
        "figure_files": {path.name: _sha256(path) for path in files},
    }
    metadata_path = output_dir / "figure_exp2_delay_appendix_metadata.json"
    write_json(metadata, metadata_path)
    return {"figure_files": files, "source_data": source_path, "metadata": metadata_path}


def _metric_value(cohort_summary: pd.DataFrame, metric: str) -> Any:
    rows = cohort_summary.loc[cohort_summary["metric"].eq(metric), "value"]
    if rows.empty:
        raise KeyError(f"Cohort summary is missing metric: {metric}")
    return rows.iloc[0]


def _count_share(count: int, total: int) -> str:
    share = count / total if total > 0 else float("nan")
    return f"{count:,} ({share:.1%})"


def _cohort_display_table(
    cohort_summary: pd.DataFrame, bootstrap_audit: dict[str, Any]
) -> pd.DataFrame:
    retained = int(float(_metric_value(cohort_summary, "retained_journey_count")))
    ambiguous = int(float(_metric_value(cohort_summary, "ambiguous_journey_count")))
    rows = [
        ("Retained conversion journeys", f"{retained:,}"),
        ("Retained user IDs", f"{int(float(_metric_value(cohort_summary, 'retained_user_count'))):,}"),
        ("Eligible campaigns", f"{int(float(_metric_value(cohort_summary, 'eligible_campaign_count'))):,}"),
        ("Eligible campaign-day cells", f"{int(float(_metric_value(cohort_summary, 'eligible_decision_cell_count'))):,}"),
        (
            "Journeys with 1 candidate cell",
            _count_share(int(float(_metric_value(cohort_summary, "candidate_cells_1_count"))), retained),
        ),
        (
            "Journeys with 2 candidate cells",
            _count_share(int(float(_metric_value(cohort_summary, "candidate_cells_2_count"))), retained),
        ),
        (
            "Journeys with 3+ candidate cells",
            _count_share(int(float(_metric_value(cohort_summary, "candidate_cells_3plus_count"))), retained),
        ),
        ("Attribution-ambiguous journeys", _count_share(ambiguous, retained)),
        (
            "Candidate-cell count, median (p90)",
            f"{float(_metric_value(cohort_summary, 'candidate_cell_count_median')):.1f} "
            f"({float(_metric_value(cohort_summary, 'candidate_cell_count_p90')):.1f})",
        ),
        (
            "Minimum impressions per eligible cell",
            f"{int(float(_metric_value(cohort_summary, 'minimum_impressions_per_cell'))):,}",
        ),
        ("Resampling unit", str(bootstrap_audit["resampling_unit"])),
        ("Resampling repetitions", f"{int(bootstrap_audit['resampling_repetitions']):,}"),
        (
            "Kendall bootstrap support",
            "Frozen full-sample support"
            if bool(bootstrap_audit.get("support_frozen", False))
            else "Not frozen",
        ),
    ]
    return pd.DataFrame(rows, columns=["Cohort characteristic", "Value"])


def _interval(point: float, lower: float, upper: float, digits: int = 3) -> str:
    return f"{point:.{digits}f} [{lower:.{digits}f}, {upper:.{digits}f}]"


def _shared_interval(point: float, lower: float, upper: float, top_k: int) -> str:
    return (
        f"{_shared_count(point, top_k)}/{top_k} "
        f"[{_shared_count(lower, top_k)}, {_shared_count(upper, top_k)}]"
    )


def make_tables(
    cohort_summary: pd.DataFrame,
    arrival_displacement: pd.DataFrame,
    source_pairwise: pd.DataFrame,
    output_dir: str | Path,
    *,
    bootstrap_audit: dict[str, Any],
    cohort_flow: pd.DataFrame | None = None,
) -> list[Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    if cohort_flow is None:
        cohort = _cohort_display_table(cohort_summary, bootstrap_audit)
    else:
        cohort = cohort_flow.rename(
            columns={
                "stage": "Cohort stage",
                "journey_count": "Journey count",
                "retention_from_previous_stage": "Retention from previous stage",
                "retention_from_candidate_journeys": "Retention from candidate journeys",
            }
        ).copy()
    cohort_csv = output_dir / "table_exp2_cohort_flow.csv"
    cohort.to_csv(cohort_csv, index=False)
    paths.append(cohort_csv)
    cohort_tex = output_dir / "table_exp2_cohort_flow.tex"
    cohort_tex.write_text(cohort.to_latex(index=False, escape=True), encoding="utf-8")
    paths.append(cohort_tex)

    # Full CSV remains the reconstructable audit output.
    primary = arrival_displacement.copy()
    primary.insert(0, "route", primary["route_id"].map(route_display_label))
    primary_csv = output_dir / "table_exp2_primary_results.csv"
    primary.to_csv(primary_csv, index=False)
    paths.append(primary_csv)

    primary_display_rows: list[dict[str, object]] = []
    for row in primary.itertuples(index=False):
        top_k = int(row.top_k)
        primary_display_rows.append(
            {
                "Route": row.route,
                "Allocation TV + resampling range": _interval(
                    row.allocation_tv_vs_arrival,
                    row.allocation_tv_resampling_q025,
                    row.allocation_tv_resampling_q975,
                ),
                f"Top-{top_k} shared + resampling range": _shared_interval(
                    row.top_k_overlap_vs_arrival,
                    row.top_k_overlap_resampling_q025,
                    row.top_k_overlap_resampling_q975,
                    top_k,
                ),
                "Kendall tau-b + resampling range": _interval(
                    row.kendall_tau_b_vs_arrival,
                    row.kendall_tau_b_resampling_q025,
                    row.kendall_tau_b_resampling_q975,
                ),
                "Kendall support cells": int(row.common_active_cell_count),
                "Support frozen": "Yes" if bool(row.support_frozen) else "No",
                "Positive-credit cells": int(row.positive_credit_cell_count),
            }
        )
    primary_display = pd.DataFrame(primary_display_rows)
    primary_tex = output_dir / "table_exp2_primary_results.tex"
    primary_tex.write_text(primary_display.to_latex(index=False, escape=True), encoding="utf-8")
    paths.append(primary_tex)

    pairwise = source_pairwise.copy()
    pairwise.insert(
        0,
        "route_pair",
        [
            f"{route_display_label(row.route_left)} vs. {route_display_label(row.route_right)}"
            for row in pairwise.itertuples(index=False)
        ],
    )
    pairwise_csv = output_dir / "table_exp2_pairwise_appendix.csv"
    pairwise.to_csv(pairwise_csv, index=False)
    paths.append(pairwise_csv)

    pairwise_display_rows: list[dict[str, object]] = []
    for row in pairwise.itertuples(index=False):
        top_k = int(row.top_k)
        pairwise_display_rows.append(
            {
                "Route pair": row.route_pair,
                "Allocation TV + resampling range": _interval(
                    row.allocation_tv,
                    row.allocation_tv_resampling_q025,
                    row.allocation_tv_resampling_q975,
                ),
                f"Top-{top_k} shared + resampling range": _shared_interval(
                    row.top_k_overlap,
                    row.top_k_overlap_resampling_q025,
                    row.top_k_overlap_resampling_q975,
                    top_k,
                ),
                "Kendall tau-b + resampling range": _interval(
                    row.kendall_tau_b,
                    row.kendall_tau_b_resampling_q025,
                    row.kendall_tau_b_resampling_q975,
                ),
                "Mean journey-assignment TV": f"{row.mean_journey_assignment_tv:.3f}",
                "Common active cells": int(row.common_active_cell_count),
                "Support frozen": "Yes" if bool(row.support_frozen) else "No",
            }
        )
    pairwise_display = pd.DataFrame(pairwise_display_rows)
    pairwise_tex = output_dir / "table_exp2_pairwise_appendix.tex"
    pairwise_tex.write_text(pairwise_display.to_latex(index=False, escape=True), encoding="utf-8")
    paths.append(pairwise_tex)
    return paths

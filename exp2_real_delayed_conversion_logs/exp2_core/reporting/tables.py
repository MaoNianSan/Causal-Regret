from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from contracts import route_display_label

from .style import shared_count


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
        ("Journeys with 1 candidate cell", _count_share(int(float(_metric_value(cohort_summary, "candidate_cells_1_count"))), retained)),
        ("Journeys with 2 candidate cells", _count_share(int(float(_metric_value(cohort_summary, "candidate_cells_2_count"))), retained)),
        ("Journeys with 3+ candidate cells", _count_share(int(float(_metric_value(cohort_summary, "candidate_cells_3plus_count"))), retained)),
        ("Attribution-ambiguous journeys", _count_share(ambiguous, retained)),
        (
            "Candidate-cell count, median (p90)",
            f"{float(_metric_value(cohort_summary, 'candidate_cell_count_median')):.1f} "
            f"({float(_metric_value(cohort_summary, 'candidate_cell_count_p90')):.1f})",
        ),
        ("Minimum impressions per eligible cell", f"{int(float(_metric_value(cohort_summary, 'minimum_impressions_per_cell'))):,}"),
        ("Resampling unit", str(bootstrap_audit["resampling_unit"])),
        ("Resampling repetitions", f"{int(bootstrap_audit['resampling_repetitions']):,}"),
        (
            "Kendall bootstrap support",
            "Frozen full-sample support" if bool(bootstrap_audit.get("support_frozen", False)) else "Not frozen",
        ),
    ]
    return pd.DataFrame(rows, columns=["Cohort characteristic", "Value"])


def _interval(point: float, lower: float, upper: float, digits: int = 3) -> str:
    return f"{point:.{digits}f} [{lower:.{digits}f}, {upper:.{digits}f}]"


def _shared_interval(point: float, lower: float, upper: float, top_k: int) -> str:
    return (
        f"{shared_count(point, top_k)}/{top_k} "
        f"[{shared_count(lower, top_k)}, {shared_count(upper, top_k)}]"
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
                "Allocation TV + resampling range": _interval(row.allocation_tv_vs_arrival, row.allocation_tv_resampling_q025, row.allocation_tv_resampling_q975),
                f"Top-{top_k} shared + resampling range": _shared_interval(row.top_k_overlap_vs_arrival, row.top_k_overlap_resampling_q025, row.top_k_overlap_resampling_q975, top_k),
                "Kendall tau-b + resampling range": _interval(row.kendall_tau_b_vs_arrival, row.kendall_tau_b_resampling_q025, row.kendall_tau_b_resampling_q975),
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
                "Allocation TV + resampling range": _interval(row.allocation_tv, row.allocation_tv_resampling_q025, row.allocation_tv_resampling_q975),
                f"Top-{top_k} shared + resampling range": _shared_interval(row.top_k_overlap, row.top_k_overlap_resampling_q025, row.top_k_overlap_resampling_q975, top_k),
                "Kendall tau-b + resampling range": _interval(row.kendall_tau_b, row.kendall_tau_b_resampling_q025, row.kendall_tau_b_resampling_q975),
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

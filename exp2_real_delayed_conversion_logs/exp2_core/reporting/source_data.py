from __future__ import annotations

import numpy as np
import pandas as pd

from contracts import PRIMARY_SOURCE_ROUTE_ORDER, SCHEMA_VERSION, route_display_label


PAIR_LABELS = {
    ("first_click_or_touch", "last_click_or_touch"): "First–Last",
    ("first_click_or_touch", "linear_source_cell_credit"): "First–Linear",
    ("first_click_or_touch", "time_decay_source_cell_credit"): "First–Decay",
    ("last_click_or_touch", "linear_source_cell_credit"): "Last–Linear",
    ("last_click_or_touch", "time_decay_source_cell_credit"): "Last–Decay",
    ("linear_source_cell_credit", "time_decay_source_cell_credit"): "Linear–Decay",
}


def build_main_figure_source(
    arrival_displacement: pd.DataFrame,
    source_pairwise: pd.DataFrame,
    *,
    run_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
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
    ).rename(columns={"route_id": "route_right_source"})
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
    combined["run_id"] = run_id
    return arrival, pairwise, combined


def build_ambiguity_figure_source(ambiguity: pd.DataFrame, *, run_id: str) -> pd.DataFrame:
    source = ambiguity.loc[ambiguity["record_type"].eq("source_route_pair")].copy()
    source["display_label"] = [
        PAIR_LABELS.get((row.route_left, row.route_right), f"{row.route_left}-{row.route_right}")
        for row in source.itertuples(index=False)
    ]
    source["schema_version"] = SCHEMA_VERSION
    source["run_id"] = run_id
    return source

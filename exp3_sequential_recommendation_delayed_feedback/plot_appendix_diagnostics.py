"""Drawing functions for Exp3 appendix dependence and carrier diagnostics."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from design_contract import ROUTE_SPECS

ACTION_COLOR = "#4C72B0"


def draw_arrival_carrier(delay: pd.DataFrame, actions: pd.DataFrame, exact_rate: float) -> plt.Figure:
    fig = plt.figure(figsize=(7.25, 3.4))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.1, 1.0], wspace=0.42)
    ax_lag = fig.add_subplot(grid[0, 0])
    ax_action = fig.add_subplot(grid[0, 1])
    x = np.arange(len(delay), dtype=float)
    ax_lag.vlines(
        x,
        delay["lag_hours_p10"].to_numpy(float),
        delay["lag_hours_p90"].to_numpy(float),
        color=ACTION_COLOR,
        linewidth=2.0,
    )
    ax_lag.scatter(x, delay["lag_hours_median"], color=ACTION_COLOR, s=28)
    ax_lag.set_xticks(x, delay["delay_bin"].astype(str))
    ax_lag.set_ylabel("Source-to-carrier lag (hours)")
    ax_lag.set_xlabel("Pseudo-arrival delay bin")
    ax_lag.set_title("(a) Carrier lag distribution", loc="left", fontweight="semibold")
    ax_lag.grid(axis="y", alpha=0.18)
    actions = actions.sort_values("action_match_rate", kind="stable").reset_index(drop=True)
    y = np.arange(len(actions), dtype=float)
    rates = actions["action_match_rate"].to_numpy(float)
    ax_action.hlines(y, 0, rates, color="0.72", linewidth=2.0)
    ax_action.scatter(rates, y, color=ACTION_COLOR, s=28)
    ax_action.set_xlim(0, max(0.5, float(rates.max()) * 1.12))
    ax_action.set_yticks(y, actions["action_display_name"].astype(str))
    ax_action.set_xlabel("Source-carrier action match rate")
    ax_action.set_title("(b) Match rate by source action", loc="left", fontweight="semibold")
    ax_action.grid(axis="x", alpha=0.18)
    ax_action.text(
        0.98,
        0.04,
        f"Exact source-event match: {exact_rate:.2%}",
        transform=ax_action.transAxes,
        ha="right",
        va="bottom",
        fontsize=7,
    )
    fig.subplots_adjust(left=0.10, right=0.98, top=0.92, bottom=0.17)
    return fig


def draw_dependence_structure(
    reuse_quantiles: pd.DataFrame,
    resampling_structure: pd.DataFrame,
) -> plt.Figure:
    fig = plt.figure(figsize=(7.35, 3.5))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.25], wspace=0.42)
    ax_reuse = fig.add_subplot(grid[0, 0])
    ax_switch = fig.add_subplot(grid[0, 1])
    for split_id, group in reuse_quantiles.groupby("split_id", observed=True):
        group = group.sort_values("quantile")
        ax_reuse.plot(
            100.0 * group["quantile"].to_numpy(float),
            group["source_windows_per_outcome_event"].to_numpy(float),
            marker={"history": "o", "evaluation": "s"}.get(str(split_id), "o"),
            markersize=3.5,
            linewidth=1.1,
            label={"history": "History", "evaluation": "Evaluation"}.get(
                str(split_id), str(split_id)
            ),
        )
    ax_reuse.set_yscale("log")
    ax_reuse.set_xlabel("Outcome-event reuse quantile (%)")
    ax_reuse.set_ylabel("Source windows containing one outcome event")
    ax_reuse.set_title("(a) Overlapping-target dependence", loc="left", fontweight="semibold")
    ax_reuse.grid(alpha=0.18)
    ax_reuse.legend(frameon=False, fontsize=7)
    route_order = ["arrival_carrier", "history_mean_control", "ridge_proxy"]
    display = {route_id: ROUTE_SPECS[route_id].route_display_name for route_id in route_order}
    metrics = (
        ("support_set_switch_rate_mean", "Support set", "o"),
        ("reference_action_switch_rate_mean", "Reference action", "s"),
        ("route_selected_action_switch_rate_mean", "Selected action", "D"),
    )
    table = resampling_structure.set_index("route_id").reindex(route_order)
    y = np.arange(len(route_order), dtype=float)
    for offset, (column, label, marker) in zip(np.linspace(-0.18, 0.18, 3), metrics):
        ax_switch.scatter(table[column], y + offset, marker=marker, s=28, label=label)
    ax_switch.set_yticks(y, [display[route] for route in route_order])
    ax_switch.invert_yaxis()
    ax_switch.set_xlim(left=0.0)
    ax_switch.set_xlabel("Mean switch rate across user resamples")
    ax_switch.set_title("(b) Data-dependent selection instability", loc="left", fontweight="semibold")
    ax_switch.grid(axis="x", alpha=0.18)
    ax_switch.legend(frameon=False, fontsize=6.8, loc="lower right")
    fig.subplots_adjust(left=0.11, right=0.98, top=0.91, bottom=0.17)
    return fig


_draw_arrival_carrier = draw_arrival_carrier
_draw_dependence_structure = draw_dependence_structure

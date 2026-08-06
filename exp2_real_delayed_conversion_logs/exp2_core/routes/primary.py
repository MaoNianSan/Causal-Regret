from __future__ import annotations

import numpy as np
import pandas as pd

from contracts import ScientificInvariantError

from .metadata import attach_route_metadata, normalize_group_weights


def arrival_assignments(retained_manifest: pd.DataFrame) -> pd.DataFrame:
    frame = retained_manifest.loc[
        retained_manifest["is_primary_eligible"],
        ["journey_id", "arrival_anchor_cell_id"],
    ].rename(columns={"arrival_anchor_cell_id": "decision_cell_id"})
    frame["credit_weight"] = 1.0
    frame["source_lag_days"] = np.nan
    return attach_route_metadata(frame, "arrival_time_accounting_anchor")


def select_click_or_touch(candidates: pd.DataFrame, *, first: bool) -> pd.DataFrame:
    work = candidates.copy()
    has_click = work.groupby("journey_id", sort=False)["is_click"].transform("any")
    work["is_selection_pool"] = np.where(has_click, work["is_click"], True)
    work = work.loc[work["is_selection_pool"]].copy()
    work = work.sort_values(
        ["journey_id", "event_timestamp_utc", "campaign_id", "source_date_utc", "source_event_id"],
        ascending=[True, first, True, True, True],
        kind="stable",
    )
    selected = work.drop_duplicates("journey_id", keep="first")
    selected = selected[["journey_id", "decision_cell_id", "source_lag_days"]].copy()
    selected["credit_weight"] = 1.0
    route_id = "first_click_or_touch" if first else "last_click_or_touch"
    return attach_route_metadata(selected, route_id)


def linear_assignments(candidates: pd.DataFrame) -> pd.DataFrame:
    unique_cells = (
        candidates.groupby(["journey_id", "decision_cell_id"], sort=False, observed=True)
        .agg(source_lag_days=("source_lag_days", "mean"))
        .reset_index()
    )
    counts = unique_cells.groupby("journey_id", sort=False)["decision_cell_id"].transform("size")
    unique_cells["credit_weight"] = 1.0 / counts.astype(float)
    return attach_route_metadata(unique_cells, "linear_source_cell_credit")


def time_decay_assignments(candidates: pd.DataFrame, decay_rate_per_day: float) -> pd.DataFrame:
    if decay_rate_per_day <= 0:
        raise ScientificInvariantError("Time-decay rate must be positive.")
    cells = (
        candidates.sort_values(
            ["journey_id", "decision_cell_id", "event_timestamp_utc", "source_event_id"],
            kind="stable",
        )
        .groupby(["journey_id", "decision_cell_id"], sort=False, observed=True)
        .tail(1)[["journey_id", "decision_cell_id", "source_lag_days"]]
        .copy()
    )
    log_weight = -float(decay_rate_per_day) * cells["source_lag_days"].to_numpy(dtype=float)
    max_log = pd.Series(log_weight, index=cells.index).groupby(cells["journey_id"], sort=False).transform("max")
    raw_weight = np.exp(log_weight - max_log.to_numpy(dtype=float))
    cells["credit_weight"] = normalize_group_weights(cells, pd.Series(raw_weight, index=cells.index))
    return attach_route_metadata(cells, "time_decay_source_cell_credit")

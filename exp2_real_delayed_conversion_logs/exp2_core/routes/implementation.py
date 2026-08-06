from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from contracts import (
    ALL_ROUTE_ORDER,
    CREDIT_TOLERANCE,
    PRIMARY_ROUTE_ORDER,
    ROUTE_SPECS,
    ScientificInvariantError,
)


@dataclass(frozen=True)
class RouteBuildResult:
    assignments: pd.DataFrame
    route_summary: pd.DataFrame
    em_diagnostics: pd.DataFrame
    logged_reference_summary: pd.DataFrame


def _attach_route_metadata(frame: pd.DataFrame, route_id: str) -> pd.DataFrame:
    spec = ROUTE_SPECS[route_id]
    output = frame.copy()
    output["route_id"] = route_id
    output["analysis_tier"] = spec.analysis_tier
    output["route_role"] = spec.route_role
    output["source_bound"] = spec.source_bound
    output["deployable"] = spec.deployable
    return output


def _normalize_group_weights(frame: pd.DataFrame, raw_weight: pd.Series) -> pd.Series:
    weights = pd.to_numeric(raw_weight, errors="coerce").fillna(0.0).clip(lower=0.0)
    totals = weights.groupby(frame["journey_id"], sort=False).transform("sum")
    if totals.le(0).any():
        bad = frame.loc[totals.le(0), "journey_id"].astype(str).unique()[:5]
        raise ScientificInvariantError(f"Nonpositive route-weight totals for journeys: {bad.tolist()}")
    return weights / totals


def _aggregate_assignment_rows(
    frame: pd.DataFrame,
    *,
    route_id: str,
    raw_weight: pd.Series,
) -> pd.DataFrame:
    work = frame[["journey_id", "decision_cell_id", "source_lag_days"]].copy()
    work["row_weight"] = pd.to_numeric(raw_weight, errors="coerce").fillna(0.0)
    aggregated = (
        work.groupby(["journey_id", "decision_cell_id"], sort=False, observed=True)
        .agg(
            raw_weight=("row_weight", "sum"),
            weighted_lag_numerator=(
                "source_lag_days",
                lambda values: float(np.nansum(values.to_numpy(dtype=float))),
            ),
            source_row_count=("source_lag_days", "size"),
        )
        .reset_index()
    )
    aggregated["credit_weight"] = _normalize_group_weights(
        aggregated, aggregated["raw_weight"]
    )
    aggregated["source_lag_days"] = (
        aggregated["weighted_lag_numerator"] / aggregated["source_row_count"].clip(lower=1)
    )
    aggregated = aggregated.drop(
        columns=["raw_weight", "weighted_lag_numerator", "source_row_count"]
    )
    return _attach_route_metadata(aggregated, route_id)


def _arrival_assignments(retained_manifest: pd.DataFrame) -> pd.DataFrame:
    frame = retained_manifest.loc[
        retained_manifest["is_primary_eligible"],
        ["journey_id", "arrival_anchor_cell_id"],
    ].rename(columns={"arrival_anchor_cell_id": "decision_cell_id"})
    frame["credit_weight"] = 1.0
    frame["source_lag_days"] = np.nan
    return _attach_route_metadata(frame, "arrival_time_accounting_anchor")


def _select_click_or_touch(candidates: pd.DataFrame, *, first: bool) -> pd.DataFrame:
    work = candidates.copy()
    has_click = work.groupby("journey_id", sort=False)["is_click"].transform("any")
    work["is_selection_pool"] = np.where(has_click, work["is_click"], True)
    work = work.loc[work["is_selection_pool"]].copy()
    work = work.sort_values(
        [
            "journey_id",
            "event_timestamp_utc",
            "campaign_id",
            "source_date_utc",
            "source_event_id",
        ],
        ascending=[True, first, True, True, True],
        kind="stable",
    )
    selected = work.drop_duplicates("journey_id", keep="first")
    selected = selected[
        ["journey_id", "decision_cell_id", "source_lag_days"]
    ].copy()
    selected["credit_weight"] = 1.0
    route_id = "first_click_or_touch" if first else "last_click_or_touch"
    return _attach_route_metadata(selected, route_id)


def _linear_assignments(candidates: pd.DataFrame) -> pd.DataFrame:
    unique_cells = (
        candidates.groupby(["journey_id", "decision_cell_id"], sort=False, observed=True)
        .agg(source_lag_days=("source_lag_days", "mean"))
        .reset_index()
    )
    counts = unique_cells.groupby("journey_id", sort=False)["decision_cell_id"].transform("size")
    unique_cells["credit_weight"] = 1.0 / counts.astype(float)
    return _attach_route_metadata(unique_cells, "linear_source_cell_credit")


def _time_decay_assignments(candidates: pd.DataFrame, decay_rate_per_day: float) -> pd.DataFrame:
    if decay_rate_per_day <= 0:
        raise ScientificInvariantError("Time-decay rate must be positive.")
    # The latest eligible event within a journey-cell defines the cell's recency.
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
    cells["credit_weight"] = _normalize_group_weights(cells, pd.Series(raw_weight, index=cells.index))
    return _attach_route_metadata(cells, "time_decay_source_cell_credit")


def _softmax_by_journey(frame: pd.DataFrame, score: np.ndarray) -> np.ndarray:
    score_series = pd.Series(score, index=frame.index, dtype=float)
    maxima = score_series.groupby(frame["journey_id"], sort=False).transform("max")
    exponent = np.exp(score_series.to_numpy() - maxima.to_numpy())
    denominator = pd.Series(exponent, index=frame.index).groupby(
        frame["journey_id"], sort=False
    ).transform("sum")
    return exponent / denominator.to_numpy(dtype=float)


def _em_soft_assignments(
    candidates: pd.DataFrame,
    decision_cells: pd.DataFrame,
    em_config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cells = (
        candidates.groupby(["journey_id", "decision_cell_id"], sort=False, observed=True)
        .agg(
            source_lag_days=("source_lag_days", "min"),
            has_click=("is_click", "max"),
        )
        .reset_index()
    )
    universe = decision_cells[["decision_cell_id", "eligible_impression_count"]].copy()
    cells = cells.merge(universe, on="decision_cell_id", how="left", validate="many_to_one")
    if cells["eligible_impression_count"].isna().any():
        raise ScientificInvariantError("EM route encountered a cell outside the frozen universe.")

    prior_smoothing = float(em_config.get("prior_smoothing", 1e-6))
    exposure = cells["eligible_impression_count"].to_numpy(dtype=float)
    prior = pd.Series(exposure, index=cells.index).groupby(cells["decision_cell_id"], sort=False).mean()
    prior = (prior + prior_smoothing) / (prior.sum() + prior_smoothing * len(prior))

    max_iter = int(em_config.get("max_iter", 50))
    tolerance = float(em_config.get("tolerance", 1e-8))
    click_coefficient = float(em_config.get("click_coefficient", 0.5))
    recency_coefficient = float(em_config.get("recency_coefficient", 0.5))
    prior_strength = float(em_config.get("prior_strength", 1.0))
    diagnostics: list[dict[str, float | int | bool]] = []
    responsibilities = np.zeros(len(cells), dtype=float)

    for iteration in range(1, max_iter + 1):
        cell_prior = cells["decision_cell_id"].map(prior).to_numpy(dtype=float)
        score = (
            prior_strength * np.log(np.clip(cell_prior, prior_smoothing, None))
            + click_coefficient * cells["has_click"].to_numpy(dtype=float)
            - recency_coefficient * cells["source_lag_days"].to_numpy(dtype=float)
        )
        responsibilities = _softmax_by_journey(cells, score)
        updated = (
            pd.Series(responsibilities, index=cells.index)
            .groupby(cells["decision_cell_id"], sort=False)
            .sum()
        )
        updated = updated.reindex(prior.index, fill_value=0.0)
        updated = (updated + prior_smoothing) / (
            updated.sum() + prior_smoothing * len(updated)
        )
        delta = float(np.max(np.abs(updated.to_numpy() - prior.to_numpy())))
        diagnostics.append(
            {"iteration": iteration, "maximum_prior_change": delta, "converged": delta <= tolerance}
        )
        prior = updated
        if delta <= tolerance:
            break

    cells["credit_weight"] = responsibilities
    assignments = _attach_route_metadata(
        cells[["journey_id", "decision_cell_id", "source_lag_days", "credit_weight"]],
        "em_soft_credit",
    )
    return assignments, pd.DataFrame(diagnostics)


def _logged_reference_assignments(candidates: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    labelled = candidates.loc[candidates["is_logged_attributed"]].copy()
    if labelled.empty:
        empty = pd.DataFrame(
            columns=[
                "journey_id",
                "decision_cell_id",
                "source_lag_days",
                "credit_weight",
                "route_id",
                "analysis_tier",
                "route_role",
                "source_bound",
                "deployable",
                "ground_truth",
            ]
        )
        summary = pd.DataFrame(
            [{"metric": "unique_labelled_journey_count", "value": 0}, {"metric": "audit_status", "value": "unavailable"}]
        )
        return empty, summary

    by_journey = labelled.groupby("journey_id", sort=False, observed=True)
    cell_count = by_journey["decision_cell_id"].nunique()
    valid_ids = set(cell_count.loc[cell_count.eq(1)].index.astype(str))
    valid = labelled.loc[labelled["journey_id"].astype(str).isin(valid_ids)].copy()
    selected = (
        valid.sort_values(
            ["journey_id", "event_timestamp_utc", "source_event_id"], kind="stable"
        )
        .drop_duplicates("journey_id", keep="first")
        [["journey_id", "decision_cell_id", "source_lag_days"]]
        .copy()
    )
    selected["credit_weight"] = 1.0
    assignments = _attach_route_metadata(selected, "logged_attribution_reference")
    candidate_count = (
        candidates.loc[candidates["journey_id"].astype(str).isin(valid_ids)]
        .groupby("journey_id", sort=False)["decision_cell_id"]
        .nunique()
    )
    discriminatory_share = float(candidate_count.ge(2).mean()) if len(candidate_count) else 0.0
    status = "attribution_discriminative" if discriminatory_share > 0 else "attribution_nondiscriminative"
    summary = pd.DataFrame(
        [
            {"metric": "unique_labelled_journey_count", "value": int(len(selected))},
            {"metric": "labelled_ambiguous_journey_share", "value": discriminatory_share},
            {"metric": "audit_status", "value": status},
        ]
    )
    return assignments, summary


def validate_credit_conservation(assignments: pd.DataFrame) -> pd.DataFrame:
    if assignments.empty:
        raise ScientificInvariantError("No route assignments were constructed.")
    if assignments["credit_weight"].lt(-CREDIT_TOLERANCE).any():
        raise ScientificInvariantError("A route assignment has negative credit weight.")
    totals = (
        assignments.groupby(["route_id", "journey_id"], sort=False, observed=True)[
            "credit_weight"
        ]
        .sum()
        .reset_index(name="credit_weight_sum")
    )
    totals["absolute_error"] = (totals["credit_weight_sum"] - 1.0).abs()
    bad = totals.loc[totals["absolute_error"].gt(CREDIT_TOLERANCE)]
    if not bad.empty:
        example = bad.head(5).to_dict(orient="records")
        raise ScientificInvariantError(f"Credit conservation failed: {example}")
    return (
        totals.groupby("route_id", sort=False)
        .agg(
            assigned_journey_count=("journey_id", "nunique"),
            maximum_credit_sum_error=("absolute_error", "max"),
        )
        .reset_index()
    )


def build_attribution_routes(
    candidates: pd.DataFrame,
    journey_manifest: pd.DataFrame,
    decision_cells: pd.DataFrame,
    config: dict[str, Any],
) -> RouteBuildResult:
    retained_manifest = journey_manifest.loc[journey_manifest["is_primary_eligible"]].copy()
    retained_ids = set(retained_manifest["journey_id"].astype(str))
    candidates = candidates.loc[candidates["journey_id"].astype(str).isin(retained_ids)].copy()

    frames: list[pd.DataFrame] = [
        _arrival_assignments(retained_manifest),
        _select_click_or_touch(candidates, first=True),
        _select_click_or_touch(candidates, first=False),
        _linear_assignments(candidates),
        _time_decay_assignments(
            candidates,
            float(
                np.log(2.0)
                / float(config["routes"]["time_decay"]["half_life_days"])
            ),
        ),
    ]
    em_diagnostics = pd.DataFrame(
        columns=["iteration", "maximum_prior_change", "converged"]
    )
    if bool(config["routes"].get("run_exploratory_by_default", False)):
        em_assignments, em_diagnostics = _em_soft_assignments(
            candidates, decision_cells, config["routes"]["em"]
        )
        frames.append(em_assignments)
    logged_assignments, logged_summary = _logged_reference_assignments(candidates)
    if not logged_assignments.empty:
        frames.append(logged_assignments)

    assignments = pd.concat(frames, ignore_index=True)
    assignments["route_id"] = pd.Categorical(
        assignments["route_id"], categories=list(ALL_ROUTE_ORDER), ordered=True
    )
    assignments = assignments.sort_values(
        ["route_id", "journey_id", "decision_cell_id"], kind="stable"
    ).reset_index(drop=True)
    assignments["route_id"] = assignments["route_id"].astype("string")

    conservation = validate_credit_conservation(assignments)
    primary_expected = int(len(retained_manifest))
    primary_counts = conservation.loc[
        conservation["route_id"].isin(PRIMARY_ROUTE_ORDER)
    ]
    if primary_counts["assigned_journey_count"].ne(primary_expected).any():
        raise ScientificInvariantError(
            "Primary routes do not cover exactly the same retained journey cohort."
        )
    route_summary = conservation.merge(
        pd.DataFrame(
            [
                {
                    "route_id": route_id,
                    "display_label": ROUTE_SPECS[route_id].display_label,
                    "route_role": ROUTE_SPECS[route_id].route_role,
                    "analysis_tier": ROUTE_SPECS[route_id].analysis_tier,
                }
                for route_id in ALL_ROUTE_ORDER
            ]
        ),
        on="route_id",
        how="left",
    )
    return RouteBuildResult(
        assignments=assignments,
        route_summary=route_summary,
        em_diagnostics=em_diagnostics,
        logged_reference_summary=logged_summary,
    )

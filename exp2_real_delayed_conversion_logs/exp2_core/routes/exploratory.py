from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from contracts import ScientificInvariantError

from .metadata import attach_route_metadata


def _softmax_by_journey(frame: pd.DataFrame, score: np.ndarray) -> np.ndarray:
    score_series = pd.Series(score, index=frame.index, dtype=float)
    maxima = score_series.groupby(frame["journey_id"], sort=False).transform("max")
    exponent = np.exp(score_series.to_numpy() - maxima.to_numpy())
    denominator = pd.Series(exponent, index=frame.index).groupby(
        frame["journey_id"], sort=False
    ).transform("sum")
    return exponent / denominator.to_numpy(dtype=float)


def em_soft_assignments(
    candidates: pd.DataFrame,
    decision_cells: pd.DataFrame,
    em_config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cells = (
        candidates.groupby(["journey_id", "decision_cell_id"], sort=False, observed=True)
        .agg(source_lag_days=("source_lag_days", "min"), has_click=("is_click", "max"))
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
        updated = pd.Series(responsibilities, index=cells.index).groupby(
            cells["decision_cell_id"], sort=False
        ).sum()
        updated = updated.reindex(prior.index, fill_value=0.0)
        updated = (updated + prior_smoothing) / (updated.sum() + prior_smoothing * len(updated))
        delta = float(np.max(np.abs(updated.to_numpy() - prior.to_numpy())))
        diagnostics.append({"iteration": iteration, "maximum_prior_change": delta, "converged": delta <= tolerance})
        prior = updated
        if delta <= tolerance:
            break
    cells["credit_weight"] = responsibilities
    assignments = attach_route_metadata(
        cells[["journey_id", "decision_cell_id", "source_lag_days", "credit_weight"]],
        "em_soft_credit",
    )
    return assignments, pd.DataFrame(diagnostics)


def logged_reference_assignments(candidates: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    labelled = candidates.loc[candidates["is_logged_attributed"]].copy()
    if labelled.empty:
        empty = pd.DataFrame(
            columns=[
                "journey_id", "decision_cell_id", "source_lag_days", "credit_weight",
                "route_id", "analysis_tier", "route_role", "source_bound", "deployable", "ground_truth",
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
        valid.sort_values(["journey_id", "event_timestamp_utc", "source_event_id"], kind="stable")
        .drop_duplicates("journey_id", keep="first")
        [["journey_id", "decision_cell_id", "source_lag_days"]]
        .copy()
    )
    selected["credit_weight"] = 1.0
    assignments = attach_route_metadata(selected, "logged_attribution_reference")
    candidate_count = candidates.loc[
        candidates["journey_id"].astype(str).isin(valid_ids)
    ].groupby("journey_id", sort=False)["decision_cell_id"].nunique()
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

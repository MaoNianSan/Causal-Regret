from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from contracts import ALL_ROUTE_ORDER, PRIMARY_ROUTE_ORDER, ROUTE_SPECS, ScientificInvariantError

from .exploratory import em_soft_assignments, logged_reference_assignments
from .primary import arrival_assignments, linear_assignments, select_click_or_touch, time_decay_assignments
from .validation import validate_credit_conservation


@dataclass(frozen=True)
class RouteBuildResult:
    assignments: pd.DataFrame
    route_summary: pd.DataFrame
    em_diagnostics: pd.DataFrame
    logged_reference_summary: pd.DataFrame


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
        arrival_assignments(retained_manifest),
        select_click_or_touch(candidates, first=True),
        select_click_or_touch(candidates, first=False),
        linear_assignments(candidates),
        time_decay_assignments(
            candidates,
            float(np.log(2.0) / float(config["routes"]["time_decay"]["half_life_days"])),
        ),
    ]
    em_diagnostics = pd.DataFrame(columns=["iteration", "maximum_prior_change", "converged"])
    if bool(config["routes"].get("run_exploratory_by_default", False)):
        em_assignments, em_diagnostics = em_soft_assignments(
            candidates, decision_cells, config["routes"]["em"]
        )
        frames.append(em_assignments)
    logged_assignments, logged_summary = logged_reference_assignments(candidates)
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
    primary_counts = conservation.loc[conservation["route_id"].isin(PRIMARY_ROUTE_ORDER)]
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


__all__ = ["RouteBuildResult", "build_attribution_routes", "validate_credit_conservation"]

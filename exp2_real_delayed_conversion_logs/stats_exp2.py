from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.stats import spearmanr

from attribution_engine import ROUTE_DISPLAY, build_assignments
from src.common import (
    ci_from_values,
    ensure_output_dirs,
    load_config,
    make_output_manifest,
    normalise_conversion_identifier,
    normalise_uid_identifier,
    out_dir,
    save_run_metadata,
    write_csv,
)
from src.parallel import parallel_map

MAIN_REFERENCE_ROUTE = "arrival_bin_anchor"
MAIN_REFERENCE_LABEL = "arrival_anchor"
TOP_K_CREDITED_MASS = "top_k_credited_mass_per_1000_events"
TOP_K_COST_ADJUSTED_SCORE = "top_k_cost_adjusted_score_per_1000_events"
CREDIT_ALLOCATION_TV_PREFIX = "credit_allocation_tv_distance_vs"
TOP_K_DECISION_CELL_OVERLAP_PREFIX = "top_k_decision_cell_overlap_vs"


@dataclass(frozen=True)
class UserCreditMatrix:
    routes: tuple[str, ...]
    actions: np.ndarray
    feature_by_user: sparse.csr_matrix
    conversion_count_by_user: np.ndarray
    n_users: int
    n_conversion_events: int


def _reference_fields(reference_label: str) -> dict[str, str]:
    token = str(reference_label).strip().lower()
    return {
        "mass_difference": f"top_k_credited_mass_difference_per_1000_events_vs_{token}",
        "cost_adjusted_difference": f"top_k_cost_adjusted_score_difference_per_1000_events_vs_{token}",
        "allocation_tv": f"{CREDIT_ALLOCATION_TV_PREFIX}_{token}",
        "top_k_overlap": f"{TOP_K_DECISION_CELL_OVERLAP_PREFIX}_{token}",
        "spearman": f"spearman_rank_correlation_vs_{token}",
    }


def _action_arrays(
    exposure: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    frame = exposure.copy().sort_values("action_id", kind="stable")
    actions = pd.to_numeric(frame["action_id"], errors="coerce").astype(int).to_numpy()
    n_impressions = (
        pd.to_numeric(frame["n_impressions"], errors="coerce")
        .fillna(0)
        .to_numpy(dtype=float)
    )
    total_cost = (
        pd.to_numeric(frame.get("total_cost", 0.0), errors="coerce")
        .fillna(0)
        .to_numpy(dtype=float)
    )
    mean_cost = (
        pd.to_numeric(frame.get("mean_cost", 0.0), errors="coerce")
        .fillna(0)
        .to_numpy(dtype=float)
    )
    positive = mean_cost[np.isfinite(mean_cost) & (mean_cost > 0)]
    cost_scale = float(np.median(positive)) if positive.size else 1.0
    if len(actions) == 0 or np.any(n_impressions <= 0):
        raise RuntimeError(
            "Decision-cell exposure contract failed: no action cells or nonpositive exposure."
        )
    return actions, n_impressions, total_cost, max(cost_scale, 1e-12)


def _stable_top_k(scores: np.ndarray, actions: np.ndarray, top_k: int) -> np.ndarray:
    order = np.lexsort((actions, -scores))
    return order[: min(int(top_k), len(order))]


def _score_arrays(
    credits: np.ndarray,
    n_impressions: np.ndarray,
    total_cost: np.ndarray,
    cost_scale: float,
    cost_lambda: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    credit_rate = np.divide(
        credits,
        n_impressions[None, :],
        out=np.full_like(credits, -np.inf),
        where=n_impressions[None, :] > 0,
    )
    mean_cost_scaled = (
        np.divide(
            total_cost,
            n_impressions,
            out=np.zeros_like(total_cost),
            where=n_impressions > 0,
        )
        / cost_scale
    )
    scores = credit_rate - float(cost_lambda) * mean_cost_scaled[None, :]
    return credit_rate, mean_cost_scaled, scores


def _metrics_from_credit(
    credits: np.ndarray,
    routes: list[str],
    actions: np.ndarray,
    n_impressions: np.ndarray,
    total_cost: np.ndarray,
    cost_scale: float,
    n_events: float,
    top_k: int,
    cost_lambda: float,
    reference_route: str,
    reference_label: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Route-specific credit-allocation summaries.

    The primary numbers are logged credit summaries.  They are deliberately not
    named utility or policy value because no policy intervention is identified
    from this observational conversion log.
    """
    if n_events <= 0:
        raise RuntimeError(
            "At least one conversion event is required for logged attribution metrics."
        )
    if top_k >= len(actions):
        raise RuntimeError(
            f"Top-k diagnostic is degenerate: top_k={top_k} must be strictly below action-cell universe={len(actions)}."
        )

    credit_rate, mean_cost_scaled, scores = _score_arrays(
        credits, n_impressions, total_cost, cost_scale, cost_lambda
    )
    route_to_index = {route: index for index, route in enumerate(routes)}
    if reference_route not in route_to_index:
        raise ValueError(f"Reference route absent: {reference_route}")

    selected = {
        route: _stable_top_k(scores[index], actions, top_k)
        for route, index in route_to_index.items()
    }
    ref_index = route_to_index[reference_route]
    reference_selected = selected[reference_route]
    reference_scores = scores[ref_index]
    reference_allocation = np.divide(
        credits[ref_index],
        max(float(credits[ref_index].sum()), 1e-12),
    )
    fields = _reference_fields(reference_label)

    rows: list[dict] = []
    action_rows: list[dict] = []
    for route, index in route_to_index.items():
        route_selected = selected[route]
        credited_mass = float(np.sum(credits[index, route_selected]))
        cost_adjusted_score = float(
            np.sum(
                credits[index, route_selected]
                - float(cost_lambda) * total_cost[route_selected] / cost_scale
            )
        )
        corr = (
            1.0
            if route == reference_route
            else float(spearmanr(scores[index], reference_scores).statistic)
        )
        if not np.isfinite(corr):
            corr = np.nan
        overlap = len(set(route_selected).intersection(reference_selected)) / float(
            top_k
        )
        allocation = np.divide(credits[index], max(float(credits[index].sum()), 1e-12))
        allocation_tv = 0.5 * float(np.abs(allocation - reference_allocation).sum())
        rows.append(
            {
                "route": route,
                "method_display_name": ROUTE_DISPLAY.get(route, route),
                "reference_route": reference_route,
                "reference_label": reference_label,
                "top_k": int(top_k),
                "cost_lambda": float(cost_lambda),
                "n_eligible_conversion_events": float(n_events),
                TOP_K_CREDITED_MASS: 1000.0 * credited_mass / n_events,
                TOP_K_COST_ADJUSTED_SCORE: 1000.0 * cost_adjusted_score / n_events,
                fields["mass_difference"]: 1000.0
                * (credited_mass - np.sum(credits[ref_index, reference_selected]))
                / n_events,
                fields["cost_adjusted_difference"]: 1000.0
                * (
                    cost_adjusted_score
                    - np.sum(
                        credits[ref_index, reference_selected]
                        - float(cost_lambda)
                        * total_cost[reference_selected]
                        / cost_scale
                    )
                )
                / n_events,
                fields["allocation_tv"]: allocation_tv,
                fields["top_k_overlap"]: float(overlap),
                fields["spearman"]: corr,
                "top_action_id": int(actions[route_selected[0]]),
                "top_action_score": float(scores[index, route_selected[0]]),
            }
        )
        selected_set = set(route_selected)
        for action_index, action_id in enumerate(actions):
            action_rows.append(
                {
                    "route": route,
                    "action_id": int(action_id),
                    "attributed_conversion_mass": float(credits[index, action_index]),
                    "n_impressions": float(n_impressions[action_index]),
                    "total_cost": float(total_cost[action_index]),
                    "credited_conversion_rate": float(credit_rate[index, action_index]),
                    "decision_cell_selection_score": float(scores[index, action_index]),
                    "in_route_top_k": int(action_index in selected_set),
                    "top_k": int(top_k),
                    "cost_lambda": float(cost_lambda),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(action_rows)


def _user_credit_matrix(
    assignments: pd.DataFrame,
    conversions: pd.DataFrame,
    routes: list[str],
    actions: np.ndarray,
) -> UserCreditMatrix:
    route_index = {route: index for index, route in enumerate(routes)}
    action_index = {int(action): index for index, action in enumerate(actions)}
    conversion_uid = conversions[["conversion_id", "uid"]].copy()
    conversion_uid["conversion_id"] = normalise_conversion_identifier(
        conversion_uid["conversion_id"]
    )
    conversion_uid["uid"] = normalise_uid_identifier(conversion_uid["uid"])
    invalid = conversion_uid["conversion_id"].isna() | conversion_uid["uid"].isna()
    if invalid.any():
        raise RuntimeError(
            f"UID bootstrap contract failed: {int(invalid.sum())} conversion reference rows have missing identifiers."
        )
    uid_counts = conversion_uid.groupby("conversion_id", sort=False)["uid"].nunique(
        dropna=True
    )
    if uid_counts.ne(1).any():
        raise RuntimeError(
            "UID bootstrap contract failed: cross-UID conversions remain; "
            f"examples={uid_counts[uid_counts.ne(1)].index[:5].tolist()}"
        )
    conversion_uid = conversion_uid.drop_duplicates(
        "conversion_id", keep="first"
    ).copy()
    conversion_uid["conversion_id"] = conversion_uid["conversion_id"].astype(str)
    conversion_uid["uid"] = conversion_uid["uid"].astype(str)

    frame = assignments[assignments["route"].isin(routes)].copy()
    frame["conversion_id"] = normalise_conversion_identifier(frame["conversion_id"])
    frame["uid"] = normalise_uid_identifier(frame["uid"])
    frame["candidate_action_id"] = pd.to_numeric(
        frame["candidate_action_id"], errors="coerce"
    )
    bad = (
        frame["conversion_id"].isna()
        | frame["uid"].isna()
        | frame["candidate_action_id"].isna()
    )
    if bad.any():
        raise RuntimeError(
            f"UID bootstrap contract failed: {int(bad.sum())} assignment rows have missing identifiers/action IDs."
        )
    frame["conversion_id"] = frame["conversion_id"].astype(str)
    frame["uid"] = frame["uid"].astype(str)
    frame["candidate_action_id"] = frame["candidate_action_id"].astype(int)
    assigned = frame.merge(
        conversion_uid.rename(columns={"uid": "expected_uid"}),
        on="conversion_id",
        how="left",
        validate="many_to_one",
    )
    missing_reference = assigned["expected_uid"].isna()
    uid_mismatch = assigned["expected_uid"].notna() & assigned["uid"].ne(
        assigned["expected_uid"]
    )
    if missing_reference.any() or uid_mismatch.any():
        examples = (
            assigned.loc[
                missing_reference | uid_mismatch,
                ["conversion_id", "uid", "expected_uid"],
            ]
            .head(5)
            .to_dict(orient="records")
        )
        raise RuntimeError(
            "UID bootstrap contract failed: assignment/reference incompatibility; "
            f"missing_reference={int(missing_reference.sum())}, "
            f"uid_mismatch={int(uid_mismatch.sum())}, examples={examples}"
        )
    if (
        assigned["route"].map(route_index).isna().any()
        or assigned["candidate_action_id"].map(action_index).isna().any()
    ):
        raise RuntimeError(
            "Sparse credit matrix contract failed: unknown route or action-cell ID."
        )
    users = np.sort(conversion_uid["uid"].unique())
    user_index = {user: index for index, user in enumerate(users)}
    conversion_count = (
        conversion_uid.groupby("uid")["conversion_id"]
        .nunique()
        .reindex(users, fill_value=0)
        .to_numpy(dtype=float)
    )
    row = assigned["uid"].map(user_index)
    if row.isna().any():
        raise RuntimeError(
            "Sparse credit matrix contract failed: UID factorisation yielded unmapped rows."
        )
    columns = assigned["route"].map(route_index).to_numpy(dtype=np.int64) * len(
        actions
    ) + assigned["candidate_action_id"].map(action_index).to_numpy(dtype=np.int64)
    values = (
        pd.to_numeric(assigned["weight"], errors="coerce")
        .fillna(0.0)
        .to_numpy(dtype=float)
    )
    matrix = sparse.coo_matrix(
        (values, (row.to_numpy(dtype=np.int64), columns)),
        shape=(len(users), len(routes) * len(actions)),
    ).tocsr()
    return UserCreditMatrix(
        tuple(routes),
        actions,
        matrix.transpose().tocsr(),
        conversion_count,
        len(users),
        int(len(conversion_uid)),
    )


def _credit_totals(
    matrix: UserCreditMatrix, user_counts: np.ndarray | None = None
) -> tuple[np.ndarray, float]:
    if user_counts is None:
        user_counts = np.ones(matrix.n_users, dtype=float)
    flat = np.asarray(
        matrix.feature_by_user @ np.asarray(user_counts, dtype=float)
    ).ravel()
    return flat.reshape(len(matrix.routes), len(matrix.actions)), float(
        np.dot(user_counts, matrix.conversion_count_by_user)
    )


def _bootstrap_matrix(
    matrix: UserCreditMatrix,
    routes: list[str],
    actions: np.ndarray,
    n_impressions: np.ndarray,
    total_cost: np.ndarray,
    cost_scale: float,
    cfg: dict,
    seed_offset: int = 0,
) -> pd.DataFrame:
    bootstrap_cfg = cfg["statistics"]["uid_bootstrap"]
    n_bootstrap = int(bootstrap_cfg["n_bootstrap"])
    seed_base = int(bootstrap_cfg["seed_base"])
    top_k = int(cfg["action"]["main_top_k"])
    fields = _reference_fields(MAIN_REFERENCE_LABEL)
    output_fields = [
        TOP_K_CREDITED_MASS,
        fields["mass_difference"],
        fields["allocation_tv"],
        fields["top_k_overlap"],
        fields["spearman"],
    ]

    def one(replicate: int) -> pd.DataFrame:
        rng = np.random.default_rng(
            np.random.SeedSequence([seed_base, seed_offset, int(replicate)])
        )
        sampled = rng.integers(0, matrix.n_users, size=matrix.n_users, endpoint=False)
        counts = np.bincount(sampled, minlength=matrix.n_users).astype(float)
        credits, n_events = _credit_totals(matrix, counts)
        metrics, _ = _metrics_from_credit(
            credits,
            routes,
            actions,
            n_impressions,
            total_cost,
            cost_scale,
            n_events,
            top_k,
            0.0,
            MAIN_REFERENCE_ROUTE,
            MAIN_REFERENCE_LABEL,
        )
        metrics["bootstrap_replicate"] = int(replicate)
        return metrics[["bootstrap_replicate", "route", *output_fields]]

    result = pd.concat(
        parallel_map(one, range(n_bootstrap), cfg, purpose="bootstrap"),
        ignore_index=True,
    )
    return result.sort_values(
        ["bootstrap_replicate", "route"], kind="stable"
    ).reset_index(drop=True)


def _add_bootstrap_intervals(
    summary: pd.DataFrame,
    bootstrap: pd.DataFrame,
    level: float,
    metric_fields: list[str],
) -> pd.DataFrame:
    result = summary.copy()
    for field in metric_fields:
        lows, highs = [], []
        for route in result["route"]:
            lo, hi = ci_from_values(
                bootstrap.loc[bootstrap["route"].eq(route), field].to_numpy(
                    dtype=float
                ),
                level,
            )
            lows.append(lo)
            highs.append(hi)
        result[f"{field}_ci_lower"] = lows
        result[f"{field}_ci_upper"] = highs
    result["ci_level"] = float(level)
    return result


def _pairwise_route_divergence(
    assignments: pd.DataFrame, routes: list[str]
) -> pd.DataFrame:
    frame = assignments[assignments["route"].isin(routes)][
        ["route", "conversion_id", "candidate_action_id", "weight"]
    ].copy()
    rows: list[dict] = []
    for left, right in combinations(routes, 2):
        a = frame[frame["route"].eq(left)][
            ["conversion_id", "candidate_action_id", "weight"]
        ].rename(columns={"weight": "weight_left"})
        b = frame[frame["route"].eq(right)][
            ["conversion_id", "candidate_action_id", "weight"]
        ].rename(columns={"weight": "weight_right"})
        merged = a.merge(
            b, on=["conversion_id", "candidate_action_id"], how="outer"
        ).fillna(0.0)
        tv = (
            0.5
            * merged.assign(diff=(merged["weight_left"] - merged["weight_right"]).abs())
            .groupby("conversion_id", sort=False)["diff"]
            .sum()
        )
        rows.append(
            {
                "route_left": left,
                "route_right": right,
                "n_conversion_events": int(tv.size),
                "mean_total_variation_distance": float(tv.mean()),
                "exact_assignment_duplicate": bool(
                    np.allclose(tv.to_numpy(dtype=float), 0.0, atol=1e-12)
                ),
            }
        )
    return pd.DataFrame(rows)


def _pairwise_route_divergence_matrix(
    assignments: pd.DataFrame, routes: list[str]
) -> pd.DataFrame:
    pair = _pairwise_route_divergence(assignments, routes)
    value = {
        (str(row.route_left), str(row.route_right)): float(
            row.mean_total_variation_distance
        )
        for row in pair.itertuples()
    }
    rows: list[dict] = []
    for left in routes:
        for right in routes:
            tv = (
                0.0
                if left == right
                else value.get((left, right), value.get((right, left), np.nan))
            )
            rows.append(
                {
                    "route_left": left,
                    "route_right": right,
                    "pairwise_credit_allocation_tv_distance": float(tv),
                }
            )
    return pd.DataFrame(rows)


def _pairwise_top_k_overlap(
    credits: np.ndarray,
    routes: list[str],
    actions: np.ndarray,
    n_impressions: np.ndarray,
    total_cost: np.ndarray,
    cost_scale: float,
    n_events: float,
    top_k_values: list[int],
) -> pd.DataFrame:
    """Pairwise decision-cell set overlap; an appendix ranking-support diagnostic."""
    _, _, scores = _score_arrays(credits, n_impressions, total_cost, cost_scale, 0.0)
    route_to_index = {route: index for index, route in enumerate(routes)}
    rows: list[dict] = []
    for top_k in top_k_values:
        if int(top_k) >= len(actions):
            raise RuntimeError(
                f"Top-k diagnostic is degenerate: top_k={top_k} must be strictly below action-cell universe={len(actions)}."
            )
        selected = {
            route: _stable_top_k(scores[index], actions, int(top_k))
            for route, index in route_to_index.items()
        }
        for left in routes:
            for right in routes:
                overlap = len(
                    set(selected[left]).intersection(selected[right])
                ) / float(top_k)
                rows.append(
                    {
                        "top_k": int(top_k),
                        "route_left": left,
                        "route_right": right,
                        "pairwise_top_k_overlap": float(overlap),
                        "n_eligible_conversion_events": int(n_events),
                    }
                )
    return pd.DataFrame(rows)


def _route_agreement(
    audit_assignments: pd.DataFrame, routes: list[str], reference: str
) -> pd.DataFrame:
    truth = (
        audit_assignments[audit_assignments["route"].eq(reference)][
            ["conversion_id", "candidate_action_id"]
        ]
        .drop_duplicates("conversion_id")
        .rename(columns={"candidate_action_id": "reference_action_id"})
    )
    rows = []
    for route in routes:
        x = audit_assignments[audit_assignments["route"].eq(route)].merge(
            truth, on="conversion_id", how="inner"
        )
        mass = float(
            x.loc[x["candidate_action_id"].eq(x["reference_action_id"]), "weight"].sum()
            / max(truth["conversion_id"].nunique(), 1)
        )
        rows.append(
            {
                "route": route,
                "source_linked_reference": reference,
                "n_conversion_events": int(truth["conversion_id"].nunique()),
                "source_action_match_mass": mass,
                "attribution_error_mass": 1.0 - mass,
            }
        )
    return pd.DataFrame(rows)


def _audit_summary(
    assignments: pd.DataFrame,
    conversions: pd.DataFrame,
    routes: list[str],
    actions: np.ndarray,
    n_impressions: np.ndarray,
    total_cost: np.ndarray,
    cost_scale: float,
    cfg: dict,
) -> pd.DataFrame:
    matrix = _user_credit_matrix(assignments, conversions, routes, actions)
    credits, n_events = _credit_totals(matrix)
    metrics, _ = _metrics_from_credit(
        credits,
        routes,
        actions,
        n_impressions,
        total_cost,
        cost_scale,
        n_events,
        int(cfg["action"]["main_top_k"]),
        0.0,
        "source_linked_reference",
        "source_linked_reference",
    )
    return metrics.merge(
        _route_agreement(assignments, routes, "source_linked_reference"),
        on="route",
        how="left",
    )


def _delay_profile(
    candidates: pd.DataFrame,
    main_conversions: pd.DataFrame,
    candidate_window_days: float,
) -> pd.DataFrame:
    """Summarize source-to-conversion delay over eligible source-event rows.

    A conversion journey can contain several source events in different delay
    buckets.  Panel A is therefore a source-event composition, not a unique
    conversion-journey distribution.
    """
    ids = set(
        normalise_conversion_identifier(main_conversions["conversion_id"])
        .dropna()
        .astype(str)
    )
    frame = candidates.copy()
    frame["conversion_id"] = normalise_conversion_identifier(frame["conversion_id"])
    frame = frame[
        frame["conversion_id"].notna() & frame["conversion_id"].astype(str).isin(ids)
    ].copy()
    values = pd.to_numeric(frame["delay_to_conversion_days"], errors="coerce")
    labels = ["less_equal_1h", "h1_to_h6", "h6_to_h24", "d1_to_d7", "d7_to_d30"]
    bins = [-np.inf, 1 / 24, 6 / 24, 1.0, 7.0, float(candidate_window_days) + 1e-12]
    frame["delay_bucket"] = pd.cut(
        values, bins=bins, labels=labels, include_lowest=True
    )
    frame = frame[frame["delay_bucket"].notna()].copy()
    result = (
        frame.groupby("delay_bucket", observed=False)
        .size()
        .rename("n_eligible_source_events")
        .reset_index()
    )
    result["cohort_id"] = "all_conversion_candidates"
    result["candidate_window_days"] = float(candidate_window_days)
    result["delay_bucket"] = result["delay_bucket"].astype(str)
    total = max(int(result["n_eligible_source_events"].sum()), 1)
    result["source_event_share_percent"] = (
        100.0 * result["n_eligible_source_events"] / total
    )
    return result[
        [
            "cohort_id",
            "n_eligible_source_events",
            "candidate_window_days",
            "delay_bucket",
            "source_event_share_percent",
        ]
    ]


def _window_sensitivity(
    candidates: pd.DataFrame,
    main_conversions: pd.DataFrame,
    action_exposure: pd.DataFrame,
    actions: np.ndarray,
    n_impressions: np.ndarray,
    total_cost: np.ndarray,
    cost_scale: float,
    cfg: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute common-cohort candidate-window diagnostics without nested bootstrap.

    The main Exp2 route-sensitivity figure carries the inferential UID-bootstrap
    intervals.  Candidate-window results are appendix-only common-cohort
    descriptive diagnostics.  Repeating the full UID bootstrap for every
    window adds four expensive nested resampling jobs but does not feed any
    reported confidence interval or scientific gate.  This function therefore
    reports deterministic point estimates, common-cohort coverage, and UID
    compatibility audit fields only.
    """
    routes = list(map(str, cfg["attribution_routes"]["main"]))
    windows = list(map(float, cfg["candidate_set"]["window_days_sensitivity"]))
    id_sets: dict[float, set[str]] = {}
    for window in windows:
        result = build_assignments(
            candidates,
            main_conversions,
            action_exposure,
            cfg,
            str(cfg["subsets"]["main_cohort_id"]),
            window,
            routes,
        )
        id_sets[window] = set(
            result.assignments.loc[
                result.assignments["route"].eq(MAIN_REFERENCE_ROUTE), "conversion_id"
            ].astype(str)
        )
        print(
            f"[stats] candidate-window eligibility: window={window:g}d; "
            f"available_conversions={len(id_sets[window]):,}",
            flush=True,
        )
    common_ids = set.intersection(*id_sets.values()) if id_sets else set()
    if not common_ids:
        raise RuntimeError(
            "Candidate-window common cohort is empty after intersecting eligible conversion IDs."
        )
    common_conversions = main_conversions[
        main_conversions["conversion_id"].astype(str).isin(common_ids)
    ].copy()
    print(
        f"[stats] candidate-window common cohort: conversions={len(common_conversions):,}; "
        "appendix diagnostic uses point estimates only",
        flush=True,
    )

    metrics_rows, audit_rows = [], []
    for position, window in enumerate(windows, start=1):
        started = time.monotonic()
        result = build_assignments(
            candidates,
            common_conversions,
            action_exposure,
            cfg,
            str(cfg["subsets"]["main_cohort_id"]),
            window,
            routes,
        )
        matrix = _user_credit_matrix(
            result.assignments, common_conversions, routes, actions
        )
        credits, n_events = _credit_totals(matrix)
        point, _ = _metrics_from_credit(
            credits,
            routes,
            actions,
            n_impressions,
            total_cost,
            cost_scale,
            n_events,
            int(cfg["action"]["main_top_k"]),
            0.0,
            MAIN_REFERENCE_ROUTE,
            MAIN_REFERENCE_LABEL,
        )
        point["candidate_window_days"] = window
        point["window_common_cohort_events"] = int(len(common_conversions))
        point["common_cohort_coverage"] = int(len(common_conversions)) / max(
            int(len(id_sets[window])), 1
        )
        point["window_bootstrap_replicates"] = 0
        point["window_uncertainty_status"] = (
            "not_computed_point_estimate_common_cohort_diagnostic"
        )
        metrics_rows.append(point)
        audit_rows.append(
            {
                "candidate_window_days": window,
                "n_conversion_ids_available_before_intersection": int(
                    len(id_sets[window])
                ),
                "n_conversion_ids_common_across_all_windows": int(
                    len(common_conversions)
                ),
                "n_assignment_rows": int(len(result.assignments)),
                "missing_reference": 0,
                "uid_mismatch": 0,
                "window_bootstrap_replicates": 0,
                "window_uncertainty_status": "not_computed_point_estimate_common_cohort_diagnostic",
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        )
        print(
            f"[stats] candidate-window diagnostic: {position}/{len(windows)}; "
            f"window={window:g}d; assignments={len(result.assignments):,}; "
            f"elapsed={time.monotonic() - started:.1f}s",
            flush=True,
        )
    return pd.concat(metrics_rows, ignore_index=True), pd.DataFrame(audit_rows)


def _em_assignment_diagnostic(assignments: pd.DataFrame) -> pd.DataFrame:
    em = assignments[assignments["route"].eq("soft_attribution_em")].copy()
    if em.empty:
        return pd.DataFrame(
            columns=[
                "conversion_id",
                "max_assignment_weight",
                "assignment_entropy",
                "n_assigned_decision_cells",
                "nontrivial_assignment",
            ]
        )
    rows: list[dict] = []
    for conversion_id, group in em.groupby("conversion_id", sort=False):
        weights = (
            pd.to_numeric(group["weight"], errors="coerce")
            .fillna(0.0)
            .to_numpy(dtype=float)
        )
        entropy = -float(np.sum(np.where(weights > 0, weights * np.log(weights), 0.0)))
        rows.append(
            {
                "conversion_id": conversion_id,
                "max_assignment_weight": float(weights.max()),
                "assignment_entropy": entropy,
                "n_assigned_decision_cells": int(
                    group["candidate_action_id"].nunique()
                ),
                "nontrivial_assignment": int(entropy > 1e-12),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute UID-bootstrap source-time attribution-sensitivity summaries for Experiment 2."
    )
    parser.add_argument("--config", default="config_exp2.yaml")
    args = parser.parse_args()
    cfg = load_config(args.config)
    ensure_output_dirs(cfg)
    processed, summaries, raw = (
        out_dir(cfg, "processed"),
        out_dir(cfg, "summaries"),
        out_dir(cfg, "raw"),
    )
    assignments = pd.read_csv(processed / "exp2_route_assignments.csv")
    conversions = pd.read_csv(processed / "exp2_conversion_arrivals.csv")
    candidates = pd.read_csv(processed / "exp2_candidate_sources.csv")
    action_exposure = pd.read_csv(processed / "exp2_action_exposure_cost.csv")
    actions, n_impressions, total_cost, cost_scale = _action_arrays(action_exposure)

    main_id = str(cfg["subsets"]["main_cohort_id"])
    audit_id = str(cfg["subsets"]["source_linked_audit_cohort_id"])
    main_routes = list(map(str, cfg["attribution_routes"]["main"]))
    main_conversions = conversions[conversions["main_cohort_eligible"].eq(1)].copy()
    audit_conversions = conversions[
        conversions["source_linked_audit_eligible"].eq(1)
    ].copy()
    main_assignments = assignments[
        (assignments["cohort_id"].eq(main_id)) & assignments["route"].isin(main_routes)
    ].copy()

    matrix = _user_credit_matrix(
        main_assignments, main_conversions, main_routes, actions
    )
    credits, n_events = _credit_totals(matrix)
    point, action_scores = _metrics_from_credit(
        credits,
        main_routes,
        actions,
        n_impressions,
        total_cost,
        cost_scale,
        n_events,
        int(cfg["action"]["main_top_k"]),
        0.0,
        MAIN_REFERENCE_ROUTE,
        MAIN_REFERENCE_LABEL,
    )
    bootstrap_started = time.monotonic()
    bootstrap = _bootstrap_matrix(
        matrix, main_routes, actions, n_impressions, total_cost, cost_scale, cfg
    )
    print(
        f"[stats] main UID bootstrap completed: {int(cfg['statistics']['uid_bootstrap']['n_bootstrap'])} replicates; "
        f"elapsed={time.monotonic() - bootstrap_started:.1f}s",
        flush=True,
    )
    main_metric_fields = [
        TOP_K_CREDITED_MASS,
        _reference_fields(MAIN_REFERENCE_LABEL)["mass_difference"],
        _reference_fields(MAIN_REFERENCE_LABEL)["allocation_tv"],
        _reference_fields(MAIN_REFERENCE_LABEL)["top_k_overlap"],
        _reference_fields(MAIN_REFERENCE_LABEL)["spearman"],
    ]
    summary = _add_bootstrap_intervals(
        point,
        bootstrap,
        float(cfg["statistics"]["uid_bootstrap"]["ci_level"]),
        main_metric_fields,
    )
    summary["n_bootstrap"] = int(cfg["statistics"]["uid_bootstrap"]["n_bootstrap"])
    summary["bootstrap_unit"] = "uid"
    summary["metric_formula_id"] = (
        "source_time_decision_cell_credit_allocation_distance_vs_constructed_arrival_anchor"
    )
    write_csv(summary, summaries / "exp2_route_sensitivity_summary.csv")
    write_csv(bootstrap, raw / "exp2_uid_bootstrap_replicates.csv")
    write_csv(
        action_scores.assign(cohort_id=main_id),
        processed / "exp2_action_route_scores.csv",
    )
    write_csv(
        _pairwise_route_divergence(main_assignments, main_routes),
        summaries / "exp2_main_route_divergence_audit.csv",
    )
    core_routes = list(map(str, cfg["reporting"]["core_source_routes"]))
    core_credit_rows = [main_routes.index(route) for route in core_routes]
    pairwise_tv = _pairwise_route_divergence_matrix(main_assignments, core_routes)
    pairwise_overlap = _pairwise_top_k_overlap(
        credits[core_credit_rows, :],
        core_routes,
        actions,
        n_impressions,
        total_cost,
        cost_scale,
        n_events,
        [int(cfg["action"]["main_top_k"])],
    )
    write_csv(
        pairwise_tv.merge(
            pairwise_overlap, on=["route_left", "route_right"], how="left"
        ),
        summaries / "exp2_source_route_pairwise_overlap.csv",
    )
    write_csv(
        (
            lambda pair_routes: _pairwise_top_k_overlap(
                credits[[main_routes.index(route) for route in pair_routes], :],
                pair_routes,
                actions,
                n_impressions,
                total_cost,
                cost_scale,
                n_events,
                list(map(int, cfg["action"]["sensitivity_top_k"])),
            )
        )(list(map(str, cfg["reporting"]["pairwise_overlap_routes"]))),
        summaries / "exp2_pairwise_top_k_overlap.csv",
    )
    write_csv(
        _delay_profile(
            candidates,
            main_conversions,
            float(cfg["candidate_set"]["window_days_main"]),
        ),
        summaries / "exp2_source_event_delay_profile.csv",
    )

    audit_routes = main_routes + [str(cfg["attribution_routes"]["audit_reference"])]
    audit_assignments = assignments[
        (assignments["cohort_id"].eq(audit_id))
        & assignments["route"].isin(audit_routes)
    ].copy()
    write_csv(
        _audit_summary(
            audit_assignments,
            audit_conversions,
            audit_routes,
            actions,
            n_impressions,
            total_cost,
            cost_scale,
            cfg,
        ),
        summaries / "exp2_source_linked_audit.csv",
    )

    cost_rows = []
    for lam in map(float, cfg["utility"]["cost_lambda_sensitivity"]):
        metrics, _ = _metrics_from_credit(
            credits,
            main_routes,
            actions,
            n_impressions,
            total_cost,
            cost_scale,
            n_events,
            int(cfg["action"]["main_top_k"]),
            lam,
            MAIN_REFERENCE_ROUTE,
            MAIN_REFERENCE_LABEL,
        )
        cost_rows.append(metrics)
    write_csv(
        pd.concat(cost_rows, ignore_index=True),
        summaries / "exp2_cost_adjusted_credit_score.csv",
    )

    window, window_audit = _window_sensitivity(
        candidates,
        main_conversions,
        action_exposure,
        actions,
        n_impressions,
        total_cost,
        cost_scale,
        cfg,
    )
    write_csv(window, summaries / "exp2_candidate_window_sensitivity.csv")
    write_csv(window_audit, processed / "exp2_candidate_window_uid_integrity.csv")

    write_csv(
        _em_assignment_diagnostic(main_assignments),
        summaries / "exp2_em_assignment_diagnostic.csv",
    )
    save_run_metadata(
        cfg,
        "statistics_success",
        {
            "n_main_conversion_events": int(n_events),
            "n_uid_clusters": matrix.n_users,
            "n_bootstrap": int(cfg["statistics"]["uid_bootstrap"]["n_bootstrap"]),
            "n_decision_cells": int(len(actions)),
            "action_unit": cfg["action"]["action_unit"],
            "main_metric": "credit_allocation_tv_distance_vs_arrival_anchor",
            "candidate_window_uncertainty": "not_computed_point_estimate_common_cohort_diagnostic",
        },
    )
    make_output_manifest(cfg)
    print("[stats] done", flush=True)


if __name__ == "__main__":
    main()

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from src.common import normalise_conversion_identifier, normalise_uid_identifier


ROUTE_DISPLAY = {
    "arrival_bin_anchor": "Arrival-bin anchor (diagnostic)",
    "first_click": "First click or touch",
    "last_click": "Last click or touch",
    "linear_attribution": "Linear attribution",
    "time_decay_soft": "Time-decay attribution",
    "soft_attribution_em": "EM soft attribution",
    "last_touch": "Last touch",
    "uniform_soft": "Uniform soft attribution",
    "click_prior_soft": "Click prior soft attribution",
    "source_linked_reference": "Criteo-attributed cell reference",
}

ROUTE_META = {
    "arrival_bin_anchor": ("arrival_bin", "diagnostic_control", True, False, "constructed arrival-bin modal campaign-source-day anchor"),
    "first_click": ("source_candidate", "none", False, True, "first clicked source cell; first source event if no click"),
    "last_click": ("source_candidate", "none", False, True, "last clicked source cell; last source event if no click"),
    "linear_attribution": ("source_candidate", "none", False, True, "equal credit across unique candidate source-time decision cells"),
    "time_decay_soft": ("source_candidate", "none", False, True, "credit proportional to exponential recency weight"),
    "soft_attribution_em": ("source_candidate", "diagnostic_control", True, False, "EM-style exposure-calibrated responsibility allocator"),
    "last_touch": ("source_candidate", "none", False, True, "most recent candidate source event"),
    "uniform_soft": ("source_candidate", "none", False, True, "equal credit across candidate source-event rows"),
    "click_prior_soft": ("source_candidate", "none", False, True, "recency weight multiplied by click prior"),
    "source_linked_reference": ("source_labelled", "source_linked_reference", False, False, "single Criteo-attributed candidate source cell; audit only"),
}


@dataclass(frozen=True)
class RouteBuildResult:
    assignments: pd.DataFrame
    em_diagnostic: pd.DataFrame


def _route_metadata(route: str) -> dict:
    interface, role, diagnostic, deployable, rule = ROUTE_META[route]
    return {
        "information_interface": interface,
        "reference_role": role or "none",
        "diagnostic_only": bool(diagnostic),
        "deployable": bool(deployable),
        "assignment_rule": rule,
        "method_display_name": ROUTE_DISPLAY[route],
    }


def _prepare_candidates(candidates: pd.DataFrame, conversion_ids: Iterable[str], window_days: float) -> pd.DataFrame:
    ids = set(normalise_conversion_identifier(pd.Series(list(conversion_ids), dtype="string")).dropna().astype(str))
    frame = candidates.copy()
    frame["conversion_id"] = normalise_conversion_identifier(frame["conversion_id"])
    frame["uid"] = normalise_uid_identifier(frame["uid"])
    frame = frame[frame["conversion_id"].notna() & frame["conversion_id"].astype(str).isin(ids)].copy()
    if frame["uid"].isna().any():
        raise RuntimeError("UID integrity contract violated: candidate rows with missing UID reached route assignment.")
    for column in ("action_id", "candidate_timestamp", "conversion_timestamp", "row_id", "click"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[frame["action_id"].notna() & frame["candidate_timestamp"].notna() & frame["conversion_timestamp"].notna()].copy()
    frame["action_id"] = frame["action_id"].astype(int)
    frame["delay_to_conversion_days"] = ((frame["conversion_timestamp"] - frame["candidate_timestamp"]) / 86400.0).clip(lower=0.0)
    frame = frame[frame["delay_to_conversion_days"].le(float(window_days))].copy()
    if frame.empty:
        raise RuntimeError(f"No mapped candidate rows remain within candidate window={window_days} days.")
    uid_counts = frame.groupby("conversion_id", sort=False)["uid"].nunique(dropna=True)
    invalid = uid_counts[uid_counts.ne(1)]
    if not invalid.empty:
        examples = ", ".join(map(str, invalid.index[:5]))
        raise RuntimeError(f"UID integrity contract violated: {len(invalid)} conversion IDs have non-unique UID after candidate preparation; examples={examples}")
    frame["conversion_id"] = frame["conversion_id"].astype(str)
    frame["uid"] = frame["uid"].astype(str)
    return frame.sort_values(["conversion_id", "candidate_timestamp", "row_id"], kind="stable").reset_index(drop=True)


def _hard_rows(conversions: pd.DataFrame, route: str, action_column: str, cohort_id: str) -> pd.DataFrame:
    frame = conversions[["conversion_id", "uid", "conversion_timestamp", action_column]].copy()
    frame.rename(columns={action_column: "candidate_action_id"}, inplace=True)
    frame["candidate_action_id"] = pd.to_numeric(frame["candidate_action_id"], errors="coerce")
    frame = frame.dropna(subset=["candidate_action_id"]).copy()
    frame["candidate_action_id"] = frame["candidate_action_id"].astype(int)
    frame["weight"] = 1.0
    frame["route"] = route
    frame["cohort_id"] = cohort_id
    return frame


def _row_choice_rows(candidates: pd.DataFrame, route: str, cohort_id: str, chooser) -> pd.DataFrame:
    rows: list[pd.Series] = []
    for _, group in candidates.groupby("conversion_id", sort=False):
        rows.append(chooser(group))
    chosen = pd.DataFrame(rows)
    chosen = chosen[["conversion_id", "uid", "conversion_timestamp", "action_id"]].rename(columns={"action_id": "candidate_action_id"})
    chosen["candidate_action_id"] = chosen["candidate_action_id"].astype(int)
    chosen["weight"] = 1.0
    chosen["route"] = route
    chosen["cohort_id"] = cohort_id
    return chosen


def _aggregate_weight_rows(candidates: pd.DataFrame, route: str, raw_weight: np.ndarray, cohort_id: str) -> pd.DataFrame:
    frame = candidates[["conversion_id", "uid", "conversion_timestamp", "action_id"]].copy()
    frame["raw_weight"] = np.asarray(raw_weight, dtype=float)
    frame["raw_weight"] = np.where(np.isfinite(frame["raw_weight"]) & (frame["raw_weight"] > 0), frame["raw_weight"], 0.0)
    denominator = frame.groupby("conversion_id", sort=False)["raw_weight"].transform("sum")
    frame["weight"] = np.divide(frame["raw_weight"], denominator, out=np.zeros(len(frame), dtype=float), where=denominator.to_numpy(dtype=float) > 0)
    frame = frame[frame["weight"].gt(0)].copy()
    grouped = frame.groupby(["conversion_id", "uid", "conversion_timestamp", "action_id"], as_index=False, dropna=False)["weight"].sum().rename(columns={"action_id": "candidate_action_id"})
    grouped["candidate_action_id"] = grouped["candidate_action_id"].astype(int)
    grouped["route"] = route
    grouped["cohort_id"] = cohort_id
    return grouped


def _linear_by_unique_action(candidates: pd.DataFrame, cohort_id: str) -> pd.DataFrame:
    dedup = candidates.sort_values(["conversion_id", "candidate_timestamp", "row_id"], kind="stable").drop_duplicates(["conversion_id", "action_id"], keep="first").copy()
    weights = np.ones(len(dedup), dtype=float)
    return _aggregate_weight_rows(dedup, "linear_attribution", weights, cohort_id)


def _em_weights(candidates: pd.DataFrame, action_exposure: pd.DataFrame, cfg: dict) -> tuple[np.ndarray, pd.DataFrame]:
    settings = cfg["em_soft_attribution"]
    actions = np.sort(candidates["action_id"].unique())
    action_index = {int(action): position for position, action in enumerate(actions)}
    exposure_map = action_exposure.set_index("action_id")["n_impressions"].to_dict()
    exposures = np.asarray([max(float(exposure_map.get(int(action), 0.0)), 1.0) for action in actions], dtype=float)
    action_idx = candidates["action_id"].map(action_index).to_numpy(dtype=int)
    click = pd.to_numeric(candidates.get("click", 0.0), errors="coerce").fillna(0.0).to_numpy(dtype=float)
    recency = candidates["delay_to_conversion_days"].to_numpy(dtype=float)
    click_coef = float(settings["click_coefficient"])
    recency_coef = float(settings["recency_coefficient"])
    prior = float(settings["prior_strength"])
    log_effect = np.log((1.0 + prior) / (exposures + prior))
    conversion_codes, _ = pd.factorize(candidates["conversion_id"].astype(str), sort=False)
    n_conversions = int(conversion_codes.max()) + 1
    weights = np.zeros(len(candidates), dtype=float)
    for iteration in range(int(settings["max_iter"])):
        logits = log_effect[action_idx] + click_coef * click - recency_coef * recency
        max_by_conversion = np.full(n_conversions, -np.inf, dtype=float)
        np.maximum.at(max_by_conversion, conversion_codes, logits)
        raw = np.exp(np.clip(logits - max_by_conversion[conversion_codes], -700, 700))
        sum_by_conversion = np.bincount(conversion_codes, weights=raw, minlength=n_conversions)
        weights = raw / np.maximum(sum_by_conversion[conversion_codes], 1e-12)
        credited = np.bincount(action_idx, weights=weights, minlength=len(actions))
        updated = np.log((credited + prior) / (exposures + prior))
        if float(np.max(np.abs(updated - log_effect))) <= float(settings["tolerance"]):
            log_effect = updated
            break
        log_effect = updated
    diagnostic = pd.DataFrame({"action_id": actions, "em_log_effect": log_effect, "em_exposure": exposures, "em_credited_conversion_mass": np.bincount(action_idx, weights=weights, minlength=len(actions)), "em_iterations_max": int(settings["max_iter"])})
    return weights, diagnostic


def build_assignments(candidates: pd.DataFrame, conversions: pd.DataFrame, action_exposure: pd.DataFrame, cfg: dict, cohort_id: str, window_days: float, routes: list[str]) -> RouteBuildResult:
    ids = normalise_conversion_identifier(conversions["conversion_id"])
    c = _prepare_candidates(candidates, ids.dropna().astype(str), window_days)
    valid_ids = set(c["conversion_id"])
    conv = conversions.copy()
    conv["conversion_id"] = normalise_conversion_identifier(conv["conversion_id"])
    conv["uid"] = normalise_uid_identifier(conv["uid"])
    conv = conv[conv["conversion_id"].notna() & conv["conversion_id"].astype(str).isin(valid_ids)].copy()
    if conv["uid"].isna().any():
        raise RuntimeError("UID integrity contract violated: main conversion table contains missing UID after filtering.")
    conv["conversion_id"] = conv["conversion_id"].astype(str)
    conv["uid"] = conv["uid"].astype(str)
    frames: list[pd.DataFrame] = []
    em_diagnostic = pd.DataFrame()
    for route in routes:
        if route == "arrival_bin_anchor":
            frames.append(_hard_rows(conv, route, "arrival_time_action_id", cohort_id))
        elif route == "source_linked_reference":
            frames.append(_hard_rows(conv, route, "labelled_source_action_id", cohort_id))
        elif route == "first_click":
            def first_choice(group: pd.DataFrame) -> pd.Series:
                clicked = group[pd.to_numeric(group.get("click", 0.0), errors="coerce").fillna(0).eq(1)]
                return (clicked if not clicked.empty else group).sort_values(["candidate_timestamp", "row_id"], kind="stable").iloc[0]
            frames.append(_row_choice_rows(c, route, cohort_id, first_choice))
        elif route == "last_click":
            def last_click_choice(group: pd.DataFrame) -> pd.Series:
                clicked = group[pd.to_numeric(group.get("click", 0.0), errors="coerce").fillna(0).eq(1)]
                return (clicked if not clicked.empty else group).sort_values(["candidate_timestamp", "row_id"], kind="stable").iloc[-1]
            frames.append(_row_choice_rows(c, route, cohort_id, last_click_choice))
        elif route == "last_touch":
            frames.append(_row_choice_rows(c, route, cohort_id, lambda group: group.sort_values(["candidate_timestamp", "row_id"], kind="stable").iloc[-1]))
        elif route == "linear_attribution":
            frames.append(_linear_by_unique_action(c, cohort_id))
        elif route == "uniform_soft":
            frames.append(_aggregate_weight_rows(c, route, np.ones(len(c), dtype=float), cohort_id))
        elif route == "time_decay_soft":
            lam = float(cfg["soft_attribution"]["time_decay_lambda_main"])
            frames.append(_aggregate_weight_rows(c, route, np.exp(-lam * c["delay_to_conversion_days"].to_numpy(dtype=float)), cohort_id))
        elif route == "click_prior_soft":
            lam = float(cfg["soft_attribution"]["time_decay_lambda_main"])
            alpha = float(cfg["soft_attribution"]["click_prior_alpha_main"])
            raw = np.exp(-lam * c["delay_to_conversion_days"].to_numpy(dtype=float)) * (1.0 + alpha * pd.to_numeric(c.get("click", 0.0), errors="coerce").fillna(0.0).to_numpy(dtype=float))
            frames.append(_aggregate_weight_rows(c, route, raw, cohort_id))
        elif route == "soft_attribution_em":
            weights, em_diagnostic = _em_weights(c, action_exposure, cfg)
            frames.append(_aggregate_weight_rows(c, route, weights, cohort_id))
        else:
            raise ValueError(f"Unsupported attribution route: {route}")
    result = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True)
    if result.empty:
        raise RuntimeError(f"No route assignments constructed for cohort={cohort_id}.")
    result["conversion_id"] = normalise_conversion_identifier(result["conversion_id"])
    result["uid"] = normalise_uid_identifier(result["uid"])
    if result["conversion_id"].isna().any() or result["uid"].isna().any():
        raise RuntimeError("UID/conversion identifier integrity contract violated in route assignments.")
    result["conversion_id"] = result["conversion_id"].astype(str)
    result["uid"] = result["uid"].astype(str)
    result["weight"] = pd.to_numeric(result["weight"], errors="coerce").fillna(0.0)
    meta = pd.DataFrame([{"route": route, **_route_metadata(route)} for route in sorted(result["route"].unique())])
    result = result.merge(meta, on="route", how="left", validate="many_to_one")
    result["candidate_window_days"] = float(window_days)
    result["fixed_horizon_eligible"] = "not_applicable"
    result["artifact_role"] = "logged_attribution_assignment"
    return RouteBuildResult(result.sort_values(["cohort_id", "route", "conversion_id", "candidate_action_id"], kind="stable").reset_index(drop=True), em_diagnostic)


def route_specification_table() -> pd.DataFrame:
    rows = []
    for route in ROUTE_META:
        rows.append({"route": route, **_route_metadata(route)})
    return pd.DataFrame(rows)

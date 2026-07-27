"""Full-design support preflight run inside fast without changing the fast estimand."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from audit_design import summarize_support_table
from config import DEFAULT_CONFIG, ExperimentConfig
from utilities import save_frame, save_json, stable_group


def _attach_group(frame: pd.DataFrame, group_count: int, cfg: ExperimentConfig) -> pd.DataFrame:
    out = frame.copy()
    out["preflight_user_group_id"] = out[cfg.user_col].map(
        lambda value: stable_group(value, group_count, cfg.group_hash_salt)
    ).astype(np.int16)
    return out


def _support_cells(
    frame: pd.DataFrame,
    actions: list[str],
    group_count: int,
    threshold: int,
    cfg: ExperimentConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    grouped = _attach_group(frame, group_count, cfg)
    valid = grouped[
        grouped["is_target_eligible"]
        & grouped["full_design_action_id"].isin(actions)
    ].copy()
    counts = (
        valid.groupby(
            ["calendar_day", "preflight_user_group_id", "reference_fold_id", "full_design_action_id"],
            observed=True,
        )
        .size()
        .rename("event_count")
        .reset_index()
    )
    days = sorted(grouped["calendar_day"].astype(str).unique().tolist())
    index = pd.MultiIndex.from_product(
        [days, range(group_count), range(cfg.reference_fold_count), actions],
        names=["calendar_day", "preflight_user_group_id", "reference_fold_id", "full_design_action_id"],
    )
    complete = counts.set_index(index.names).reindex(index, fill_value=0).reset_index()
    complete = complete.rename(columns={"full_design_action_id": "action_id"})
    pivot = complete.pivot_table(
        index=["calendar_day", "preflight_user_group_id", "action_id"],
        columns="reference_fold_id",
        values="event_count",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    for fold_id in range(cfg.reference_fold_count):
        if fold_id not in pivot.columns:
            pivot[fold_id] = 0
    pivot = pivot.rename(columns={0: "fold_0_count", 1: "fold_1_count"})
    pivot["minimum_fold_count"] = pivot[["fold_0_count", "fold_1_count"]].min(axis=1)
    pivot["support_threshold"] = int(threshold)
    pivot["support_ratio"] = pivot["minimum_fold_count"] / float(threshold)
    pivot["is_supported_action"] = pivot["minimum_fold_count"] >= threshold
    pivot["audit_unit_id"] = (
        pivot["calendar_day"].astype(str)
        + "__group_"
        + pivot["preflight_user_group_id"].astype(int).astype(str).str.zfill(2)
    )

    unit = (
        pivot.groupby(["calendar_day", "preflight_user_group_id", "audit_unit_id"], observed=True)
        .agg(supported_action_count=("is_supported_action", "sum"))
        .reset_index()
    )
    action_count = len(actions)
    unit["action_coverage"] = unit["supported_action_count"] / float(action_count)
    unit["pair_coverage"] = np.where(
        unit["supported_action_count"] >= 2,
        (unit["supported_action_count"] - 1) / float(max(action_count - 1, 1)),
        0.0,
    )
    unit["is_valid_audit_unit"] = unit["supported_action_count"] >= 2
    return pivot, unit, summarize_support_table(unit)


def _action_summary(cells: pd.DataFrame) -> pd.DataFrame:
    if cells.empty:
        return pd.DataFrame()
    return (
        cells.groupby("action_id", observed=True)
        .agg(
            audit_unit_count=("audit_unit_id", "nunique"),
            supported_unit_rate=("is_supported_action", "mean"),
            minimum_fold_count_min=("minimum_fold_count", "min"),
            minimum_fold_count_p10=("minimum_fold_count", lambda x: float(np.quantile(x, 0.10))),
            minimum_fold_count_median=("minimum_fold_count", "median"),
            minimum_fold_count_p90=("minimum_fold_count", lambda x: float(np.quantile(x, 0.90))),
            minimum_fold_count_max=("minimum_fold_count", "max"),
        )
        .reset_index()
    )


def run_full_design_support_preflight(
    history: pd.DataFrame,
    evaluation: pd.DataFrame,
    full_actions: list[str],
    output_dir: Path,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
    *,
    synthetic_fixture: bool = False,
) -> dict[str, object]:
    required_action_count = cfg.action_top_k_full
    if len(full_actions) < required_action_count:
        status = "NOT_EVALUATED_FIXTURE_INSUFFICIENT_ACTIONS" if synthetic_fixture else "BLOCKED_INSUFFICIENT_ACTIONS"
        payload = {
            "status": status,
            "full_design_support_ready": False,
            "required_action_count": required_action_count,
            "available_action_count": len(full_actions),
            "selected_user_group_count": None,
            "display_user_group_count": None,
            "support_threshold": cfg.support_min_events_per_fold_full,
        }
        save_json(payload, output_dir / "diagnostics" / "exp3_full_design_support_preflight.json")
        save_frame(pd.DataFrame(), output_dir / "tables" / "exp3_full_design_support_preflight.csv")
        save_frame(pd.DataFrame(), output_dir / "derived" / "exp3_full_design_support_cells.csv")
        save_frame(pd.DataFrame(), output_dir / "derived" / "exp3_full_design_support_by_action.csv")
        return payload

    actions = list(full_actions[:required_action_count])
    history_rows: list[dict[str, object]] = []
    candidates: dict[int, tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]] = {}
    selected_group: int | None = None
    for group_count in cfg.user_group_candidates_full:
        cells, units, summary = _support_cells(
            history,
            actions,
            group_count,
            cfg.support_min_events_per_fold_full,
            cfg,
        )
        passes = all(
            float(summary[key]) >= cfg.history_support_pass_threshold
            for key in ("action_coverage", "pair_coverage", "audit_unit_coverage")
        )
        history_rows.append(
            {
                "split_id": "history",
                "user_group_count": group_count,
                **summary,
                "passes_history_support_gate": passes,
            }
        )
        candidates[group_count] = (cells, units, summary)
        if passes and selected_group is None:
            selected_group = group_count

    if selected_group is None:
        display_group = max(
            cfg.user_group_candidates_full,
            key=lambda g: sum(float(candidates[g][2][key]) for key in ("action_coverage", "pair_coverage", "audit_unit_coverage")),
        )
    else:
        display_group = selected_group
    evaluation_cells, _, evaluation_summary = _support_cells(
        evaluation,
        actions,
        display_group,
        cfg.support_min_events_per_fold_full,
        cfg,
    )
    action_summary = _action_summary(evaluation_cells)
    evaluation_pass_floor = all(
        float(evaluation_summary[key]) >= cfg.support_limited_threshold
        for key in ("action_coverage", "pair_coverage", "audit_unit_coverage")
    )
    evaluation_full_pass = all(
        float(evaluation_summary[key]) >= cfg.history_support_pass_threshold
        for key in ("action_coverage", "pair_coverage", "audit_unit_coverage")
    )
    if selected_group is None:
        status = "BLOCKED_HISTORY_SUPPORT"
    elif not evaluation_pass_floor:
        status = "BLOCKED_EVALUATION_SUPPORT"
    elif evaluation_full_pass:
        status = "READY"
    else:
        status = "READY_WITH_LIMITED_SUPPORT"
    support_ready = status in {"READY", "READY_WITH_LIMITED_SUPPORT"}

    summary_table = pd.DataFrame(
        [
            *history_rows,
            {
                "split_id": "evaluation",
                "user_group_count": display_group,
                **evaluation_summary,
                "passes_history_support_gate": np.nan,
            },
        ]
    )
    payload = {
        "status": status,
        "full_design_support_ready": support_ready,
        "required_action_count": required_action_count,
        "available_action_count": len(full_actions),
        "selected_user_group_count": selected_group,
        "display_user_group_count": display_group,
        "support_threshold": cfg.support_min_events_per_fold_full,
        "history_support_pass_threshold": cfg.history_support_pass_threshold,
        "support_limited_threshold": cfg.support_limited_threshold,
        "evaluation_action_coverage": evaluation_summary["action_coverage"],
        "evaluation_pair_coverage": evaluation_summary["pair_coverage"],
        "evaluation_audit_unit_coverage": evaluation_summary["audit_unit_coverage"],
        "selection_uses_evaluation_data": False,
    }
    save_frame(summary_table, output_dir / "tables" / "exp3_full_design_support_preflight.csv")
    save_frame(evaluation_cells, output_dir / "derived" / "exp3_full_design_support_cells.csv")
    save_frame(action_summary, output_dir / "derived" / "exp3_full_design_support_by_action.csv")
    save_json(payload, output_dir / "diagnostics" / "exp3_full_design_support_preflight.json")
    return payload

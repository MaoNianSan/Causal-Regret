"""History-only freeze of groups, support, and near-tie threshold."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, ExperimentConfig
from utilities import read_frame, save_frame, save_json, stable_group


@dataclass(frozen=True)
class AuditDesign:
    user_group_count: int
    support_min_events_per_fold: int
    near_tie_threshold: float
    candidate_actions: tuple[str, ...]
    history_support_summary: pd.DataFrame
    design_freeze: dict[str, object]


def load_audit_design(output_dir: Path) -> AuditDesign:
    freeze_path = output_dir / "design" / "exp3_design_freeze.json"
    if not freeze_path.exists():
        raise FileNotFoundError(f"Bootstrap resume requires design freeze: {freeze_path}")
    import json

    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    support = read_frame(output_dir / "design" / "exp3_history_support_audit.csv")
    return AuditDesign(
        user_group_count=int(freeze["selected_user_group_count"]),
        support_min_events_per_fold=int(freeze["support_min_events_per_fold"]),
        near_tie_threshold=float(freeze["near_tie_threshold"]),
        candidate_actions=tuple(str(value) for value in freeze["candidate_actions"]),
        history_support_summary=support,
        design_freeze=freeze,
    )



def summarize_support_table(support_table: pd.DataFrame) -> dict[str, float | int]:
    """Aggregate support metrics with equal weight over every audit unit."""
    if support_table.empty:
        return {
            "action_coverage": 0.0,
            "pair_coverage": 0.0,
            "audit_unit_coverage": 0.0,
            "supported_action_count_mean": 0.0,
            "total_audit_unit_count": 0,
            "valid_audit_unit_count": 0,
        }
    return {
        "action_coverage": float(support_table["action_coverage"].mean()),
        "pair_coverage": float(support_table["pair_coverage"].mean()),
        "audit_unit_coverage": float(support_table["is_valid_audit_unit"].astype(bool).mean()),
        "supported_action_count_mean": float(support_table["supported_action_count"].mean()),
        "total_audit_unit_count": int(len(support_table)),
        "valid_audit_unit_count": int(support_table["is_valid_audit_unit"].astype(bool).sum()),
    }

def _attach_group(frame: pd.DataFrame, group_count: int, cfg: ExperimentConfig) -> pd.DataFrame:
    out = frame.copy()
    out["user_group_id"] = out[cfg.user_col].map(
        lambda value: stable_group(value, group_count, cfg.group_hash_salt)
    ).astype(np.int16)
    out["audit_unit_id"] = out["calendar_day"].astype(str) + "__group_" + out["user_group_id"].astype(str).str.zfill(2)
    return out


def _history_support(
    history: pd.DataFrame,
    candidate_actions: list[str],
    group_count: int,
    support_threshold: int,
    cfg: ExperimentConfig,
) -> tuple[pd.DataFrame, dict[str, float], list[float]]:
    frame = _attach_group(history, group_count, cfg)
    valid = frame[frame["is_target_eligible"] & frame["action_id"].isin(candidate_actions)].copy()
    counts = (
        valid.groupby(["calendar_day", "user_group_id", "reference_fold_id", "action_id"], observed=True)
        .size()
        .rename("event_count")
        .reset_index()
    )
    values = (
        valid.groupby(["calendar_day", "user_group_id", "reference_fold_id", "action_id"], observed=True)
        .agg(
            target_sum=("future_engagement_target_6h", "sum"),
            target_count=("future_engagement_target_6h", "count"),
        )
        .reset_index()
    )
    values["target_mean"] = values["target_sum"] / values["target_count"]
    action_count = len(candidate_actions)
    rows: list[dict[str, object]] = []
    absolute_gaps: list[float] = []
    for (day, group_id), unit_counts in counts.groupby(["calendar_day", "user_group_id"], sort=True):
        pivot = unit_counts.pivot(index="action_id", columns="reference_fold_id", values="event_count").fillna(0)
        pivot = pivot.reindex(candidate_actions, fill_value=0)
        for fold in range(cfg.reference_fold_count):
            if fold not in pivot.columns:
                pivot[fold] = 0
        supported = [
            action
            for action in candidate_actions
            if all(float(pivot.loc[action, fold]) >= support_threshold for fold in range(cfg.reference_fold_count))
        ]
        action_coverage = len(supported) / action_count if action_count else np.nan
        pair_coverage = (len(supported) - 1) / (action_count - 1) if len(supported) >= 2 and action_count > 1 else 0.0
        is_valid = len(supported) >= 2
        rows.append(
            {
                "calendar_day": day,
                "user_group_id": int(group_id),
                "audit_unit_id": f"{day}__group_{int(group_id):02d}",
                "supported_action_count": len(supported),
                "action_coverage": action_coverage,
                "pair_coverage": pair_coverage,
                "is_valid_audit_unit": is_valid,
            }
        )
        if not is_valid:
            continue
        unit_values = values[(values["calendar_day"] == day) & (values["user_group_id"] == group_id)]
        value_map = {
            (int(record.reference_fold_id), str(record.action_id)): float(record.target_mean)
            for record in unit_values.itertuples()
        }
        for selection_fold, evaluation_fold in ((0, 1), (1, 0)):
            selection_values = np.array([value_map.get((selection_fold, action), np.nan) for action in supported])
            if not np.isfinite(selection_values).all():
                continue
            reference_action = supported[int(np.argmax(selection_values))]
            reference_value = value_map.get((evaluation_fold, reference_action), np.nan)
            for action in supported:
                if action == reference_action:
                    continue
                action_value = value_map.get((evaluation_fold, action), np.nan)
                if np.isfinite(reference_value) and np.isfinite(action_value):
                    absolute_gaps.append(abs(reference_value - action_value))
    support_table = pd.DataFrame(rows)
    summary = {"user_group_count": group_count, **summarize_support_table(support_table)}
    return support_table, summary, absolute_gaps


def freeze_audit_design(
    history_events: pd.DataFrame,
    evaluation_events: pd.DataFrame,
    candidate_actions: list[str],
    output_dir: Path,
    run_tier: str,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> tuple[AuditDesign, pd.DataFrame, pd.DataFrame]:
    threshold = cfg.support_min_events_per_fold(run_tier)
    candidate_summaries: list[dict[str, object]] = []
    selected: tuple[int, pd.DataFrame, dict[str, float], list[float]] | None = None
    for group_count in cfg.group_candidates(run_tier):
        table, summary, gaps = _history_support(
            history_events, candidate_actions, group_count, threshold, cfg
        )
        status = (
            summary["action_coverage"] >= cfg.history_support_pass_threshold
            and summary["pair_coverage"] >= cfg.history_support_pass_threshold
            and summary["audit_unit_coverage"] >= cfg.history_support_pass_threshold
        )
        candidate_summaries.append({**summary, "passes_history_support_gate": status})
        if status and selected is None:
            selected = (group_count, table, summary, gaps)
    if selected is None:
        raise RuntimeError(
            "History-only support audit cannot sustain the prespecified day-by-user-group action comparison design."
        )
    group_count, support_table, support_summary, gaps = selected
    positive_gaps = np.asarray([gap for gap in gaps if np.isfinite(gap) and gap > 0], dtype=float)
    if positive_gaps.size == 0:
        raise RuntimeError("History support audit produced no positive held-out action gaps.")
    near_tie_threshold = float(cfg.near_tie_multiplier * np.median(positive_gaps))
    history = _attach_group(history_events, group_count, cfg)
    evaluation = _attach_group(evaluation_events, group_count, cfg)

    users = pd.concat(
        [history[[cfg.user_col]], evaluation[[cfg.user_col]]], ignore_index=True
    ).drop_duplicates(cfg.user_col)
    users["user_group_id"] = users[cfg.user_col].map(
        lambda value: stable_group(value, group_count, cfg.group_hash_salt)
    ).astype(np.int16)
    users["reference_fold_id"] = users[cfg.user_col].map(
        lambda value: stable_group(value, cfg.reference_fold_count, cfg.reference_fold_hash_salt)
    ).astype(np.int8)

    freeze = {
        "candidate_group_counts": list(cfg.group_candidates(run_tier)),
        "selected_user_group_count": group_count,
        "support_min_events_per_fold": threshold,
        "support_threshold_is_fast_scaled": run_tier == "fast",
        "history_action_coverage": support_summary["action_coverage"],
        "history_pair_coverage": support_summary["pair_coverage"],
        "history_audit_unit_coverage": support_summary["audit_unit_coverage"],
        "history_support_pass_threshold": cfg.history_support_pass_threshold,
        "near_tie_multiplier": cfg.near_tie_multiplier,
        "near_tie_threshold": near_tie_threshold,
        "candidate_actions": candidate_actions,
        "residual_action_is_candidate": False,
        "group_hash_salt": cfg.group_hash_salt,
        "reference_fold_hash_salt": cfg.reference_fold_hash_salt,
        "reference_fold_count": cfg.reference_fold_count,
        "selection_uses_evaluation_data": False,
    }
    save_frame(pd.DataFrame(candidate_summaries), output_dir / "design" / "exp3_history_group_selection.csv")
    save_frame(support_table, output_dir / "design" / "exp3_history_support_audit.csv")
    save_frame(users, output_dir / "design" / "exp3_user_assignments.parquet")
    save_json(freeze, output_dir / "design" / "exp3_design_freeze.json")
    design = AuditDesign(
        user_group_count=group_count,
        support_min_events_per_fold=threshold,
        near_tie_threshold=near_tie_threshold,
        candidate_actions=tuple(candidate_actions),
        history_support_summary=support_table,
        design_freeze=freeze,
    )
    return design, history, evaluation

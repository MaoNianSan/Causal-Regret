"""Common-support definitions and summaries for Experiment 3."""
from __future__ import annotations

import numpy as np
import pandas as pd


def reference_pair_coverage(supported_action_count: int, action_count: int) -> float:
    if supported_action_count < 2 or action_count <= 1:
        return 0.0
    return (supported_action_count - 1) / (action_count - 1)


def support_record(
    source_count: np.ndarray,
    threshold: int,
    day: str,
    group_id: int,
    candidate_actions: tuple[str, ...],
) -> tuple[np.ndarray, dict[str, object], list[dict[str, object]]]:
    common_supported = np.all(source_count >= threshold, axis=0)
    supported_indices = np.flatnonzero(common_supported)
    action_count = len(candidate_actions)
    pair_coverage = reference_pair_coverage(len(supported_indices), action_count)
    audit_unit_id = f"{day}__group_{group_id:02d}"
    record = {
        "calendar_day": day,
        "user_group_id": group_id,
        "audit_unit_id": audit_unit_id,
        "supported_action_count": len(supported_indices),
        "action_coverage": len(supported_indices) / action_count,
        "reference_pair_coverage": pair_coverage,
        "pair_coverage": pair_coverage,
        "is_valid_audit_unit": len(supported_indices) >= 2,
    }
    margins = []
    for action_idx, action_id in enumerate(candidate_actions):
        fold_counts = source_count[:, action_idx].astype(float)
        minimum = float(np.min(fold_counts))
        margins.append(
            {
                "calendar_day": day,
                "user_group_id": group_id,
                "audit_unit_id": audit_unit_id,
                "action_id": action_id,
                "fold_0_count": float(fold_counts[0]),
                "fold_1_count": float(fold_counts[1]),
                "minimum_fold_count": minimum,
                "support_threshold": float(threshold),
                "support_ratio": minimum / threshold if threshold > 0 else np.nan,
                "support_margin": minimum - float(threshold),
                "is_supported_action": bool(common_supported[action_idx]),
            }
        )
    return supported_indices, record, margins


def summarize_support_table(support_table: pd.DataFrame) -> dict[str, float | int]:
    if support_table.empty:
        return {
            "action_coverage": 0.0,
            "reference_pair_coverage": 0.0,
            "pair_coverage": 0.0,
            "audit_unit_coverage": 0.0,
            "supported_action_count_mean": 0.0,
            "total_audit_unit_count": 0,
            "valid_audit_unit_count": 0,
        }
    pair = float(support_table["reference_pair_coverage"].mean())
    return {
        "action_coverage": float(support_table["action_coverage"].mean()),
        "reference_pair_coverage": pair,
        "pair_coverage": pair,
        "audit_unit_coverage": float(support_table["is_valid_audit_unit"].astype(bool).mean()),
        "supported_action_count_mean": float(support_table["supported_action_count"].mean()),
        "total_audit_unit_count": int(len(support_table)),
        "valid_audit_unit_count": int(support_table["is_valid_audit_unit"].astype(bool).sum()),
    }

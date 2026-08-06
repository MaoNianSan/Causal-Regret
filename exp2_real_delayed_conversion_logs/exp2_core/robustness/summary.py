from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def build_robustness_summary(targeted: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    completed = targeted.loc[targeted["analysis_status"].eq("COMPLETED")].copy()
    rows: list[dict[str, object]] = []
    primary_specs = {
        "candidate_window_days": config["cohort"]["primary_candidate_window_days"],
        "minimum_impressions": config["decision_cell"]["minimum_impressions"],
        "top_k": config["ranking"]["primary_top_k"],
        "time_decay_half_life_days": config["routes"]["time_decay"]["half_life_days"],
    }
    for (dimension, record_type), group in completed.groupby(
        ["targeted_dimension", "record_type"], sort=False, dropna=False
    ):
        allocation = pd.to_numeric(group.get("allocation_tv"), errors="coerce").dropna()
        kendall = pd.to_numeric(group.get("kendall_tau_b"), errors="coerce").dropna()
        overlap = pd.to_numeric(group.get("top_k_overlap"), errors="coerce").dropna()
        alternatives = sorted({str(value) for value in group["targeted_value"].dropna()})
        rows.append(
            {
                "dimension": dimension,
                "primary_specification": primary_specs.get(str(dimension)),
                "alternative_specification": "|".join(alternatives),
                "comparison_group": record_type,
                "allocation_tv_min": float(allocation.min()) if len(allocation) else np.nan,
                "allocation_tv_max": float(allocation.max()) if len(allocation) else np.nan,
                "kendall_tau_b_min": float(kendall.min()) if len(kendall) else np.nan,
                "kendall_tau_b_max": float(kendall.max()) if len(kendall) else np.nan,
                "top_k_overlap_min": float(overlap.min()) if len(overlap) else np.nan,
                "top_k_overlap_max": float(overlap.max()) if len(overlap) else np.nan,
                "qualitative_conclusion_preserved": bool(
                    (allocation.gt(0).any() if len(allocation) else False)
                    or (kendall.lt(1).any() if len(kendall) else False)
                ),
            }
        )
    return pd.DataFrame(rows)

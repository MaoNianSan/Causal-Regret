"""Equal-audit-unit aggregation of canonical Exp3 metrics."""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import ExperimentConfig
from design_contract import route_metadata
from score_metrics import summarize_score_metrics


DIRECTION_MEAN_METRICS = (
    "maximum_heldout_reference_pair_gap_error",
    "mean_absolute_reference_pair_gap_error",
    "p90_absolute_reference_pair_gap_error",
    "heldout_reference_pair_sign_agreement",
    "near_tie_pair_share",
    "signed_cross_fitted_reference_minus_route_value_difference",
    "top_action_agreement_with_fold_reference",
)


def summarize_route_metrics(
    unit_table: pd.DataFrame,
    cell_table: pd.DataFrame,
    cfg: ExperimentConfig,
) -> pd.DataFrame:
    rows = []
    for route_id in cfg.primary_route_ids:
        units = unit_table[unit_table["route_id"] == route_id]
        cells = cell_table[cell_table["route_id"] == route_id]
        aggregations = {metric: (metric, "mean") for metric in DIRECTION_MEAN_METRICS}
        aggregations.update(
            {
                "valid_reference_pair_count": ("valid_reference_pair_count", "sum"),
                "near_tie_pair_count": ("near_tie_pair_count", "sum"),
                "valid_direction_count": ("selection_fold_id", "count"),
            }
        )
        unit_averages = units.groupby("audit_unit_id", observed=True).agg(**aggregations)
        row: dict[str, object] = {"route_id": route_id, **route_metadata(route_id)}
        row.update(summarize_score_metrics(cells))
        for metric in DIRECTION_MEAN_METRICS:
            row[metric] = float(unit_averages[metric].mean())
        row["valid_reference_pair_count"] = int(unit_averages["valid_reference_pair_count"].sum())
        row["near_tie_pair_count"] = int(unit_averages["near_tie_pair_count"].sum())
        valid_pairs = int(row["valid_reference_pair_count"])
        row["near_tie_pair_share"] = (
            int(row["near_tie_pair_count"]) / valid_pairs if valid_pairs else np.nan
        )
        row["valid_audit_unit_count"] = int(len(unit_averages))
        row["valid_direction_count"] = int(unit_averages["valid_direction_count"].sum())
        row.update(
            {
                "heldout_gap_defect": row["maximum_heldout_reference_pair_gap_error"],
                "gap_sign_agreement": row["heldout_reference_pair_sign_agreement"],
                "gap_reversal_rate": 1.0 - float(row["heldout_reference_pair_sign_agreement"]),
                "valid_gap_pair_count": row["valid_reference_pair_count"],
                "cross_fitted_ranking_shortfall": row[
                    "signed_cross_fitted_reference_minus_route_value_difference"
                ],
                "top_action_match_rate": row["top_action_agreement_with_fold_reference"],
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)

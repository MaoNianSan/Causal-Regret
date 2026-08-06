"""Read-only audit of the frozen six-hour target and its components."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, ExperimentConfig
from utilities import save_frame


COMPONENTS = (
    ("long_view", "long_view"),
    ("like", "is_like"),
    ("comment", "is_comment"),
    ("forward", "is_forward"),
    ("follow", "is_follow"),
)


def audit_target_components(
    frame: pd.DataFrame,
    split_id: str,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """Return diagnostics without mutating the constructed target frame."""
    target = frame["future_engagement_target_6h"].to_numpy(float, copy=True)
    raw_target = frame["future_engagement_value_6h"].to_numpy(float, copy=True)
    eligible = frame["is_target_eligible"].fillna(False).to_numpy(bool, copy=True)
    rows: list[dict[str, object]] = []
    finite_target = target[np.isfinite(target)]
    for statistic, value in (
        ("count", len(finite_target)),
        ("mean", float(np.mean(finite_target)) if finite_target.size else np.nan),
        ("std", float(np.std(finite_target)) if finite_target.size else np.nan),
        ("p50", float(np.quantile(finite_target, 0.50)) if finite_target.size else np.nan),
        ("p90", float(np.quantile(finite_target, 0.90)) if finite_target.size else np.nan),
        ("p99", float(np.quantile(finite_target, 0.99)) if finite_target.size else np.nan),
    ):
        rows.append(
            {
                "split_id": split_id,
                "record_type": "target_distribution",
                "component_id": "constructed_target",
                "statistic": statistic,
                "value": value,
            }
        )
    contributions = []
    for component_id, column in COMPONENTS:
        values = frame[column].to_numpy(float, copy=True)
        weight = float(cfg.future_value_weights[component_id])
        contribution = float(np.sum(values * weight))
        contributions.append((component_id, column, values, weight, contribution))
    total_contribution = sum(record[4] for record in contributions)
    for component_id, column, values, weight, contribution in contributions:
        rows.append(
            {
                "split_id": split_id,
                "record_type": "component",
                "component_id": component_id,
                "source_column": column,
                "component_weight": weight,
                "nonzero_rate": float(np.mean(values != 0)) if len(values) else 0.0,
                "raw_weighted_contribution": contribution,
                "contribution_share": contribution / total_contribution if total_contribution else 0.0,
                "longview_shared_component_disclosure": (
                    "long_view is a shared constructed-target component, not an identified causal label"
                    if component_id == "long_view"
                    else ""
                ),
            }
        )
    formula_matches = bool(
        np.allclose(
            target[eligible],
            np.log1p(raw_target[eligible]),
            equal_nan=True,
        )
    )
    rows.append(
        {
            "split_id": split_id,
            "record_type": "contract",
            "component_id": "target_contract",
            "target_interval": "[t,t+6h)",
            "right_censored_count": int((~eligible).sum()),
            "eligible_target_count": int(eligible.sum()),
            "constructed_formula": "log1p(future_engagement_value_6h)",
            "constructed_formula_matches": formula_matches,
            "target_horizon_hours": cfg.target_horizon_hours,
        }
    )
    return pd.DataFrame(rows)


def write_target_component_audit(
    history: pd.DataFrame,
    evaluation: pd.DataFrame,
    output_dir: Path,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    audit = pd.concat(
        [
            audit_target_components(history, "history", cfg),
            audit_target_components(evaluation, "evaluation", cfg),
        ],
        ignore_index=True,
        sort=False,
    )
    save_frame(audit, output_dir / "tables" / "exp3_target_component_audit.csv")
    return audit

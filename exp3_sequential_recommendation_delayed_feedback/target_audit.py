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
TARGET_QUANTILES = (
    ("p0", 0.0),
    ("p25", 0.25),
    ("p50", 0.50),
    ("p75", 0.75),
    ("p90", 0.90),
    ("p95", 0.95),
    ("p99", 0.99),
)


def _component_window_sums(
    frame: pd.DataFrame,
    cfg: ExperimentConfig,
) -> dict[str, np.ndarray]:
    required = {cfg.user_col, cfg.time_col, *(column for _, column in COMPONENTS)}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Target component audit is missing columns: {sorted(missing)}")
    working = frame.reset_index(drop=True)
    totals = {
        component_id: np.full(len(working), np.nan, dtype=float)
        for component_id, _ in COMPONENTS
    }
    for _, group in working.groupby(cfg.user_col, sort=False):
        ordered = group.sort_values(cfg.time_col, kind="stable")
        positions = ordered.index.to_numpy(int)
        times = ordered[cfg.time_col].to_numpy(np.int64)
        left = np.searchsorted(times, times, side="left")
        right = np.searchsorted(times, times + cfg.target_horizon_ms, side="left")
        for component_id, column in COMPONENTS:
            values = ordered[column].to_numpy(float)
            cumulative = np.concatenate([[0.0], np.cumsum(values)])
            totals[component_id][positions] = cumulative[right] - cumulative[left]
    return totals


def audit_target_components(
    frame: pd.DataFrame,
    split_id: str,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """Return diagnostics without mutating the constructed target frame."""
    working = frame.reset_index(drop=True)
    target = working["future_engagement_target_6h"].to_numpy(float, copy=True)
    raw_target = working["future_engagement_value_6h"].to_numpy(float, copy=True)
    eligible = working["is_target_eligible"].fillna(False).to_numpy(bool, copy=True)
    window_sums = _component_window_sums(working, cfg)
    rows: list[dict[str, object]] = []
    finite_target = target[eligible & np.isfinite(target)]
    quantiles = {
        statistic: float(np.quantile(finite_target, quantile))
        if finite_target.size
        else np.nan
        for statistic, quantile in TARGET_QUANTILES
    }
    summary = {
        "split_id": split_id,
        "record_type": "target_summary",
        "component_id": "constructed_target",
        "eligible_source_event_count": int(eligible.sum()),
        "right_censored_count": int((~eligible).sum()),
        "target_zero_rate": float(np.mean(finite_target == 0)) if finite_target.size else np.nan,
        "target_mean": float(np.mean(finite_target)) if finite_target.size else np.nan,
        "target_std": float(np.std(finite_target)) if finite_target.size else np.nan,
        "target_interval": "[t,t+6h)",
        **{f"target_{key}": value for key, value in quantiles.items()},
    }
    rows.append(summary)
    distribution = (
        ("count", len(finite_target)),
        ("mean", float(np.mean(finite_target)) if finite_target.size else np.nan),
        ("std", float(np.std(finite_target)) if finite_target.size else np.nan),
        ("zero_rate", summary["target_zero_rate"]),
        *quantiles.items(),
    )
    for statistic, value in distribution:
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
        values = window_sums[component_id][eligible]
        weight = float(cfg.future_value_weights[component_id])
        weighted = values * weight
        contribution_total = float(np.sum(weighted))
        contribution_mean = float(np.mean(weighted)) if len(weighted) else np.nan
        contributions.append(
            (component_id, column, values, weight, contribution_mean, contribution_total)
        )
    total_contribution = sum(record[5] for record in contributions)
    for component_id, column, values, weight, contribution_mean, contribution_total in contributions:
        rows.append(
            {
                "split_id": split_id,
                "record_type": "component",
                "component_id": component_id,
                "source_column": column,
                "component_weight": weight,
                "nonzero_rate": float(np.mean(values != 0)) if len(values) else 0.0,
                "component_window_sum_mean": float(np.mean(values)) if len(values) else np.nan,
                "raw_weighted_contribution": contribution_mean,
                "raw_weighted_contribution_total": contribution_total,
                "contribution_share": contribution_total / total_contribution
                if total_contribution
                else 0.0,
                "long_view_shared_with_proxy": component_id == "long_view",
                "longview_shared_component_disclosure": (
                    "long_view is a shared constructed-target component, not an identified causal label"
                    if component_id == "long_view"
                    else ""
                ),
            }
        )
    reconstructed_raw = sum(
        float(cfg.future_value_weights[component_id]) * values
        for component_id, values in window_sums.items()
    )
    component_formula_matches = bool(
        np.allclose(raw_target[eligible], reconstructed_raw[eligible], equal_nan=True)
    )
    target_formula_matches = bool(
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
            "constructed_formula_matches": target_formula_matches,
            "component_formula_matches": component_formula_matches,
            "long_view_shared_with_proxy": True,
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

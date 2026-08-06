"""Module A shared-seed summaries, paired contrasts, and precision gate."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from exp4.configuration.parameters import MODULE_A, REPORTING
from exp4.metrics.monte_carlo import mean_mcse, percentile_interval


METRICS = (
    "population_action_gap_defect",
    "route_optimal_set_conflict_rate",
    "pairwise_gap_sign_disagreement_rate",
    "margin_certificate_rate",
)


def _bootstrap_mean_interval(
    values: np.ndarray, bootstrap_replications: int, seed: int
) -> tuple[float, float]:
    if bootstrap_replications <= 0:
        return np.nan, np.nan
    rng = np.random.default_rng(np.random.SeedSequence(seed))
    positions = rng.integers(0, len(values), size=(bootstrap_replications, len(values)))
    return percentile_interval(
        np.mean(values[positions], axis=1), REPORTING.confidence_level
    )


def summarize_population(
    seed_level: pd.DataFrame, bootstrap_replications: int
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    groups = seed_level.groupby(
        ["route_id", "route_label_rate", "attribution_proxy_noise_sd"],
        sort=True,
        dropna=False,
    )
    for group_index, (keys, group) in enumerate(groups):
        group = group.sort_values("seed")
        record = {
            "route_id": keys[0],
            "route_label_rate": keys[1],
            "attribution_proxy_noise_sd": keys[2],
            "shared_seed_count": int(group["seed"].nunique()),
        }
        for metric_index, metric in enumerate(METRICS):
            values = group[metric].to_numpy(dtype=np.float64)
            lower, upper = _bootstrap_mean_interval(
                values,
                bootstrap_replications,
                REPORTING.bootstrap_seed + group_index * 100 + metric_index,
            )
            record[f"{metric}_mean"] = float(np.mean(values))
            record[f"{metric}_sd"] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
            record[f"{metric}_mcse"] = mean_mcse(values)
            record[f"{metric}_ci_lower"] = lower
            record[f"{metric}_ci_upper"] = upper
        records.append(record)
    return pd.DataFrame.from_records(records)


def _contrast_record(
    family: str,
    contrast_id: str,
    fixed_parameter: str,
    level_from: float,
    level_to: float,
    differences: np.ndarray,
    expected_direction: str,
    bootstrap_replications: int,
    seed: int,
) -> dict[str, Any]:
    lower, upper = _bootstrap_mean_interval(differences, bootstrap_replications, seed)
    agreement = differences < 0.0 if expected_direction == "decrease" else differences > 0.0
    return {
        "contrast_family": family,
        "contrast_id": contrast_id,
        "fixed_parameter": fixed_parameter,
        "level_from": level_from,
        "level_to": level_to,
        "paired_mean_difference": float(np.mean(differences)),
        "paired_sd": float(np.std(differences, ddof=1)) if len(differences) > 1 else 0.0,
        "paired_mcse": mean_mcse(differences),
        "ci_lower": lower,
        "ci_upper": upper,
        "direction_agreement_rate": float(np.mean(agreement)),
        "exact_zero_rate": float(np.mean(np.isclose(differences, 0.0, atol=1e-12))),
        "non_finite_count": int(np.sum(~np.isfinite(differences))),
        "shared_seed_count": int(len(differences)),
        "expected_direction": expected_direction,
    }


def summarize_paired_contrasts(
    seed_level: pd.DataFrame,
    bootstrap_replications: int,
    run_tier: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    primary = seed_level[seed_level["route_id"] == "proxy_label"].copy()
    records: list[dict[str, Any]] = []
    counter = 0
    for sigma in MODULE_A.proxy_noise_sds:
        fixed = primary[np.isclose(primary["attribution_proxy_noise_sd"], sigma)]
        pivot = fixed.pivot(index="seed", columns="route_label_rate", values="population_action_gap_defect")
        for level_from, level_to in zip(MODULE_A.route_label_rates[:-1], MODULE_A.route_label_rates[1:], strict=True):
            differences = (pivot[level_to] - pivot[level_from]).to_numpy(dtype=float)
            records.append(
                _contrast_record(
                    "route_label_rate",
                    f"q_{level_from:g}_to_{level_to:g}__sigma_{sigma:g}",
                    f"sigma_proxy={sigma:g}",
                    level_from,
                    level_to,
                    differences,
                    "decrease",
                    bootstrap_replications,
                    REPORTING.bootstrap_seed + 10_000 + counter,
                )
            )
            counter += 1
    for route_label_rate in MODULE_A.route_label_rates:
        fixed = primary[np.isclose(primary["route_label_rate"], route_label_rate)]
        pivot = fixed.pivot(index="seed", columns="attribution_proxy_noise_sd", values="population_action_gap_defect")
        for level_from, level_to in zip(MODULE_A.proxy_noise_sds[:-1], MODULE_A.proxy_noise_sds[1:], strict=True):
            differences = (pivot[level_to] - pivot[level_from]).to_numpy(dtype=float)
            records.append(
                _contrast_record(
                    "proxy_noise_sd",
                    f"sigma_{level_from:g}_to_{level_to:g}__q_{route_label_rate:g}",
                    f"q_route={route_label_rate:g}",
                    level_from,
                    level_to,
                    differences,
                    "increase",
                    bootstrap_replications,
                    REPORTING.bootstrap_seed + 10_000 + counter,
                )
            )
            counter += 1
    contrasts = pd.DataFrame.from_records(records)
    primary_id = "q_0.7_to_1__sigma_0.25"
    contrasts["is_primary_contrast"] = contrasts["contrast_id"].eq(primary_id)
    contrasts["primary_contrast_half_width"] = np.nan
    contrasts["primary_contrast_relative_half_width"] = np.nan
    contrasts["monte_carlo_precision_gate"] = "NOT_APPLICABLE_NON_FULL"
    primary_rows = contrasts["is_primary_contrast"]
    if not primary_rows.empty:
        index = primary_rows.index[0]
        row = contrasts.loc[index]
        half_width = (
            0.5 * float(row["ci_upper"] - row["ci_lower"])
            if np.isfinite(row["ci_lower"]) and np.isfinite(row["ci_upper"])
            else 1.96 * float(row["paired_mcse"])
        )
        effect = abs(float(row["paired_mean_difference"]))
        relative = half_width / effect if effect > 0.0 else np.inf
        contrasts.loc[index, "primary_contrast_half_width"] = half_width
        contrasts.loc[index, "primary_contrast_relative_half_width"] = relative
        if run_tier == "full":
            threshold = max(0.005, 0.10 * effect)
            contrasts.loc[index, "monte_carlo_precision_gate"] = (
                "PASS" if half_width <= threshold else "STOP_AND_REVIEW"
            )
    direction = (
        contrasts.groupby(["contrast_family", "expected_direction"], sort=True)
        .agg(
            contrast_count=("contrast_id", "count"),
            mean_direction_agreement=("direction_agreement_rate", "mean"),
            minimum_direction_agreement=("direction_agreement_rate", "min"),
            mean_exact_zero_rate=("exact_zero_rate", "mean"),
        )
        .reset_index()
    )
    return contrasts, direction

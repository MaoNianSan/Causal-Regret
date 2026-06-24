"""Aggregate Exp4 outputs and generate seed-level percentile-bootstrap confidence intervals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

import config

METRICS = [
    "causal_regret_per_round",
    "causal_regret_all_rounds",
    "final_causal_regret",
    "proxy_state_error_per_round",
    "absolute_proxy_distortion_per_round",
    "proxy_ranking_reversal_rate",
    "mean_delay",
    "pending_at_horizon",
    "pending_fraction",
    "source_state_mismatch",
    "ranking_reversal_rate",
    "wrong_assignment_rate",
    "labelled_arrival_fraction",
    "oracle_normalized_recovery",
    "source_labelled_normalized_recovery",
    "source_binding_advantage",
]


def _rng_offset(values: Iterable[object]) -> int:
    return sum(sum(ord(ch) for ch in str(value)) for value in values)


def bootstrap_mean_ci(
    values: np.ndarray, *, formal: bool, seed_offset: int
) -> tuple[float, float]:
    if not formal or len(values) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(config.BOOTSTRAP_SEED + seed_offset)
    indices = rng.integers(0, len(values), size=(config.BOOTSTRAP_N, len(values)))
    draws = values[indices].mean(axis=1)
    alpha = (1.0 - config.CI_LEVEL) / 2.0
    return float(np.quantile(draws, alpha)), float(np.quantile(draws, 1.0 - alpha))


def summarize(df: pd.DataFrame, by: list[str], *, formal: bool) -> pd.DataFrame:
    rows: list[dict] = []
    for keys, group in df.groupby(by, dropna=False, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(by, keys))
        row["n_seeds"] = (
            int(group["seed"].nunique()) if "seed" in group else int(len(group))
        )
        row["n_rows"] = int(len(group))
        for metric in METRICS:
            if metric not in group:
                continue
            values = group[metric].dropna().to_numpy(float)
            if not len(values):
                continue
            row[f"{metric}_mean"] = float(values.mean())
            row[f"{metric}_se"] = (
                float(values.std(ddof=1) / np.sqrt(len(values)))
                if len(values) > 1
                else float("nan")
            )
            ci_low, ci_high = bootstrap_mean_ci(
                values, formal=formal, seed_offset=_rng_offset([*keys, metric])
            )
            row[f"{metric}_ci_low"] = ci_low
            row[f"{metric}_ci_high"] = ci_high
        row["ci_level"] = config.CI_LEVEL if formal else np.nan
        row["uncertainty_unit"] = (
            "shared_simulation_seed_percentile_bootstrap"
            if formal
            else "fast_preview_point_estimate_only"
        )
        row["n_bootstrap"] = config.BOOTSTRAP_N if formal else 0
        rows.append(row)
    return pd.DataFrame(rows)


def paired_comparison(
    df: pd.DataFrame,
    reference: str,
    candidate: str,
    group_cols: list[str],
    *,
    formal: bool,
) -> list[dict]:
    """Paired percentile-bootstrap CIs only; no bootstrap-derived p-values are reported."""
    results: list[dict] = []
    subset = df[df["method_id"].isin([reference, candidate])]
    for keys, group in subset.groupby(group_cols, dropna=False, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        pivot = group.pivot_table(
            index="seed",
            columns="method_id",
            values="causal_regret_per_round",
            aggfunc="first",
        ).dropna()
        if reference not in pivot or candidate not in pivot or len(pivot) < 2:
            continue
        differences = pivot[candidate].to_numpy(float) - pivot[reference].to_numpy(
            float
        )
        row = dict(zip(group_cols, keys))
        row.update(
            {
                "reference": reference,
                "candidate": candidate,
                "n_paired_seeds": int(len(differences)),
                "mean_difference_candidate_minus_reference": float(differences.mean()),
            }
        )
        if formal:
            rng = np.random.default_rng(
                config.BOOTSTRAP_SEED + _rng_offset([*keys, reference, candidate])
            )
            indices = rng.integers(
                0, len(differences), size=(config.BOOTSTRAP_N, len(differences))
            )
            draws = differences[indices].mean(axis=1)
            alpha = (1.0 - config.CI_LEVEL) / 2.0
            row.update(
                {
                    "ci_low": float(np.quantile(draws, alpha)),
                    "ci_high": float(np.quantile(draws, 1.0 - alpha)),
                    "inference_status": "formal_full_paired_percentile_bootstrap_ci",
                    "inference_note": f"Paired percentile-bootstrap confidence interval over shared seeds with {config.BOOTSTRAP_N} resamples; no p-value is reported.",
                }
            )
        else:
            row.update(
                {
                    "ci_low": np.nan,
                    "ci_high": np.nan,
                    "inference_status": "fast_preview_no_formal_inference",
                    "inference_note": "Fast uses three seeds; direction checks only, with no confidence interval or p-value.",
                }
            )
        results.append(row)
    return results


def _baseline_replicated_over_q(raw: pd.DataFrame) -> pd.DataFrame:
    base = raw[
        (raw["subexperiment_id"] == "baseline_reference")
        & raw["method_id"].eq("arrival_time_naive")
    ].copy()
    replicas: list[pd.DataFrame] = []
    for q in config.Q_GRID:
        copy = base.copy()
        copy["source_label_rate_q"] = q
        copy["setting_id"] = f"q_{q:.2f}_arrival_time_baseline"
        copy["subexperiment_id"] = "source_label_sweep"
        replicas.append(copy)
    return pd.concat(replicas, ignore_index=True)


def _phase_map(raw: pd.DataFrame) -> pd.DataFrame:
    phase = raw[raw["subexperiment_id"].eq("recoverability_phase_map")].copy()
    baseline = raw[
        (raw["subexperiment_id"] == "baseline_reference")
        & raw["method_id"].eq("arrival_time_naive")
    ][["seed", "causal_regret_per_round"]].rename(
        columns={"causal_regret_per_round": "arrival_time_regret"}
    )
    proxy_oracle = raw[
        (raw["subexperiment_id"] == "proxy_distortion_diagnostic")
        & raw["method_id"].eq("proxy_oracle_diagnostic")
    ][["seed", "causal_regret_per_round"]].rename(
        columns={"causal_regret_per_round": "proxy_oracle_regret"}
    )
    source_reference = raw[
        (raw["subexperiment_id"] == "source_label_sweep")
        & raw["method_id"].eq("source_labelled_reference")
    ][["seed", "causal_regret_per_round"]].rename(
        columns={"causal_regret_per_round": "source_labelled_reference_regret"}
    )
    phase = phase.merge(baseline, on="seed", how="left", validate="many_to_one")
    phase = phase.merge(proxy_oracle, on="seed", how="left", validate="many_to_one")
    phase = phase.merge(source_reference, on="seed", how="left", validate="many_to_one")
    oracle_denominator = phase["arrival_time_regret"] - phase["proxy_oracle_regret"]
    source_denominator = (
        phase["arrival_time_regret"] - phase["source_labelled_reference_regret"]
    )
    phase["oracle_normalized_recovery"] = (
        phase["arrival_time_regret"] - phase["causal_regret_per_round"]
    ) / oracle_denominator
    phase["oracle_normalized_recovery_denominator"] = oracle_denominator
    phase["source_labelled_normalized_recovery"] = (
        phase["arrival_time_regret"] - phase["causal_regret_per_round"]
    ) / source_denominator
    phase["source_labelled_normalized_recovery_denominator"] = source_denominator
    return phase


def _source_binding_advantage(raw: pd.DataFrame) -> pd.DataFrame:
    coupling = raw[raw["subexperiment_id"].eq("delay_state_coupling_diagnostic")]
    relevant = coupling[
        coupling["method_id"].isin(["arrival_time_naive", "source_labelled_reference"])
    ]
    pivot = relevant.pivot_table(
        index=["seed", "delay_state_coupling_beta"],
        columns="method_id",
        values="causal_regret_per_round",
        aggfunc="first",
    ).reset_index()
    diagnostics = coupling[coupling["method_id"].eq("arrival_time_naive")][
        [
            "seed",
            "delay_state_coupling_beta",
            "mean_delay",
            "pending_at_horizon",
            "pending_fraction",
            "source_state_mismatch",
            "ranking_reversal_rate",
        ]
    ].drop_duplicates(["seed", "delay_state_coupling_beta"])
    result = pivot.merge(
        diagnostics,
        on=["seed", "delay_state_coupling_beta"],
        how="inner",
        validate="one_to_one",
    )
    result["source_binding_advantage"] = (
        result["arrival_time_naive"] - result["source_labelled_reference"]
    )
    return result


def run(run_dir: Path) -> None:
    raw = pd.read_csv(run_dir / "raw" / "seed_level_results.csv")
    run_config = json.loads(
        (run_dir / "logs" / "run_config.json").read_text(encoding="utf-8")
    )
    formal = run_config["mode"] == "full"
    summaries = run_dir / "summaries"

    proxy = raw[
        (raw["subexperiment_id"] == "proxy_distortion_diagnostic")
        & raw["method_id"].eq("proxy_noisy_oracle_diagnostic")
    ].copy()
    summarize(proxy, ["method_id", "proxy_noise_sigma"], formal=formal).to_csv(
        summaries / "proxy_distortion_diagnostic_summary.csv", index=False
    )

    source = raw[raw["subexperiment_id"].eq("source_label_sweep")].copy()
    source = pd.concat([source, _baseline_replicated_over_q(raw)], ignore_index=True)
    summarize(
        source, ["method_id", "source_label_rate_q", "proxy_noise_sigma"], formal=formal
    ).to_csv(summaries / "source_label_sweep_summary.csv", index=False)

    phase = _phase_map(raw)
    phase.to_csv(summaries / "recoverability_phase_map_seed_level.csv", index=False)
    # This single summary contains both arrival-oracle and source-labelled normalization;
    # do not write a redundant second CSV with identical rows.
    summarize(
        phase, ["source_label_rate_q", "proxy_noise_sigma"], formal=formal
    ).to_csv(summaries / "recoverability_phase_map_summary.csv", index=False)

    coupling = raw[raw["subexperiment_id"].eq("delay_state_coupling_diagnostic")].copy()
    summarize(
        coupling, ["method_id", "delay_state_coupling_beta"], formal=formal
    ).to_csv(summaries / "delay_state_coupling_summary.csv", index=False)
    advantage = _source_binding_advantage(raw)
    advantage.to_csv(summaries / "source_binding_advantage_seed_level.csv", index=False)
    summarize(advantage, ["delay_state_coupling_beta"], formal=formal).to_csv(
        summaries / "source_binding_advantage_summary.csv", index=False
    )

    calibration = coupling.groupby(
        ["seed", "delay_state_coupling_beta"], as_index=False
    ).agg(
        mean_delay=("mean_delay", "first"),
        pending_at_horizon=("pending_at_horizon", "first"),
        pending_fraction=("pending_fraction", "first"),
        source_state_mismatch=("source_state_mismatch", "first"),
        ranking_reversal_rate=("ranking_reversal_rate", "first"),
    )
    calibration["target_mean_delay"] = config.TARGET_MEAN_DELAY
    calibration["exact_match"] = np.isclose(
        calibration["mean_delay"], config.TARGET_MEAN_DELAY
    )
    calibration.to_csv(summaries / "delay_calibration_audit.csv", index=False)

    tests: list[dict] = []
    tests += paired_comparison(
        source,
        "arrival_time_naive",
        "proxy_label_recovery",
        ["source_label_rate_q", "proxy_noise_sigma"],
        formal=formal,
    )
    tests += paired_comparison(
        coupling,
        "arrival_time_naive",
        "source_labelled_reference",
        ["delay_state_coupling_beta"],
        formal=formal,
    )
    pd.DataFrame(tests).to_csv(
        summaries / "paired_bootstrap_comparisons.csv", index=False
    )

    pd.DataFrame(
        [
            {
                "metric_id": "causal_regret_per_round",
                "metric_formula_id": "post_warmup_structural_regret",
                "formula": "mean_{t=warmup_t+1..T}[ell(A_t,S_t)-min_a ell(a,S_t)]",
            },
            {
                "metric_id": "proxy_state_error_per_round",
                "metric_formula_id": "mean_l2_proxy_state_error",
                "formula": "mean_t ||P_t-S_t||_2; environment-side diagnostic",
            },
            {
                "metric_id": "absolute_proxy_distortion_per_round",
                "metric_formula_id": "mean_absolute_loss_map_difference",
                "formula": "mean_{t,a}|ell(a,S_t)-ell(a,P_t)|; environment-side diagnostic",
            },
            {
                "metric_id": "oracle_normalized_recovery",
                "metric_formula_id": "arrival_oracle_normalized_recovery",
                "formula": "(R_arrival-R_route)/(R_arrival-R_proxy_oracle); raw values are not clipped",
            },
            {
                "metric_id": "source_labelled_normalized_recovery",
                "metric_formula_id": "arrival_source_labelled_normalized_recovery",
                "formula": "(R_arrival-R_route)/(R_arrival-R_source_labelled_reference); q=1 equals 1 by construction when action traces match",
            },
        ]
    ).to_csv(summaries / "metric_specification.csv", index=False)
    raw.to_csv(summaries / "full_seed_level_results.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.run_dir)


if __name__ == "__main__":
    main()

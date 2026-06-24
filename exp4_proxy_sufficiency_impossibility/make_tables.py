"""Paper-facing Exp4 tables and appendix audit tables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import aggregate_results
import config


def _mean_ci(row: pd.Series, metric: str) -> str:
    mean = row[f"{metric}_mean"]
    low = row.get(f"{metric}_ci_low")
    high = row.get(f"{metric}_ci_high")
    if pd.notna(low) and pd.notna(high):
        return f"{mean:.4f} [{low:.4f}, {high:.4f}]"
    return f"{mean:.4f} [fast preview]"


def _q_label(q: float) -> str:
    return f"{int(round(q * 1000)):03d}"


def _paired_appendix_table(run_dir: Path, summaries: Path) -> pd.DataFrame:
    run_config = json.loads(
        (run_dir / "logs" / "run_config.json").read_text(encoding="utf-8")
    )
    formal = run_config["mode"] == "full"
    existing = pd.read_csv(summaries / "paired_bootstrap_comparisons.csv")
    seed_level = pd.read_csv(summaries / "full_seed_level_results.csv")
    source = seed_level[
        seed_level["subexperiment_id"].eq("source_label_sweep")
        & seed_level["method_id"].isin(
            ["observable_history_surrogate", "proxy_label_recovery"]
        )
        & np.isclose(seed_level["source_label_rate_q"], 0.0)
        & np.isclose(seed_level["proxy_noise_sigma"], config.DEFAULT_PROXY_SIGMA)
    ].copy()
    supplemental = pd.DataFrame(
        aggregate_results.paired_comparison(
            source,
            "observable_history_surrogate",
            "proxy_label_recovery",
            ["source_label_rate_q", "proxy_noise_sigma"],
            formal=formal,
        )
    )
    if not supplemental.empty:
        existing = pd.concat([existing, supplemental], ignore_index=True, sort=False)

    rows: list[dict] = []
    for _, row in existing.iterrows():
        reference = str(row["reference"])
        candidate = str(row["candidate"])
        q = row.get("source_label_rate_q")
        sigma = row.get("proxy_noise_sigma")
        beta = row.get("delay_state_coupling_beta")
        if pd.notna(q) and pd.notna(sigma):
            q_float = float(q)
            sigma_float = float(sigma)
            setting_id = f"structural_high_beta_200_sigma_{int(round(sigma_float * 100)):03d}_q_{_q_label(q_float)}"
            comparison_id = f"{candidate}_vs_{reference}_q_{_q_label(q_float)}"
        elif pd.notna(beta):
            beta_float = float(beta)
            setting_id = f"delay_state_coupling_beta_{int(round(beta_float * 100)):03d}"
            comparison_id = (
                f"{candidate}_vs_{reference}_beta_{int(round(beta_float * 100)):03d}"
            )
        else:
            setting_id = "structural_high_beta_200"
            comparison_id = f"{candidate}_vs_{reference}"
        interpretation = "Paired percentile-bootstrap interval over shared seeds; no bootstrap pseudo-p-value is reported."
        if (
            candidate == "proxy_label_recovery"
            and reference == "observable_history_surrogate"
            and pd.notna(q)
            and np.isclose(float(q), 0.0)
        ):
            comparison_id = "proxy_label_recovery_vs_observable_history_surrogate_q_000"
            interpretation = "The proxy-label route improves on arrival-time assignment at q = 0, but does not establish a reliable advantage over the observable-history surrogate under the paired 95% interval."
        rows.append(
            {
                "comparison_id": comparison_id,
                "setting_id": setting_id,
                "metric_id": "causal_regret_per_round",
                "contrast": f"{candidate} - {reference}",
                "point_estimate": row["mean_difference_candidate_minus_reference"],
                "ci_lower": row["ci_low"],
                "ci_upper": row["ci_high"],
                "ci_level": config.CI_LEVEL if formal else np.nan,
                "n_seeds": row["n_paired_seeds"],
                "n_bootstrap": config.BOOTSTRAP_N if formal else 0,
                "interpretation": interpretation,
            }
        )
    return pd.DataFrame(rows)


def run(run_dir: Path, *, only_paired: bool = False) -> None:
    summaries = run_dir / "summaries"
    tables = run_dir / "tables"
    tables.mkdir(exist_ok=True)

    if only_paired:
        paired_table = _paired_appendix_table(run_dir, summaries)
        paired_table.to_csv(
            tables / "tbl_app_exp4_paired_bootstrap_comparisons.csv", index=False
        )
        paired_table.to_latex(
            tables / "tbl_app_exp4_paired_bootstrap_comparisons.tex",
            index=False,
            escape=True,
            float_format="%.6f",
        )
        return

    source = pd.read_csv(summaries / "source_label_sweep_summary.csv")
    source = source[
        source["method_id"].isin(
            [
                "arrival_time_naive",
                "observable_history_surrogate",
                "proxy_label_recovery",
                "source_labelled_reference",
            ]
        )
    ].copy()
    source["method_display_name"] = source["method_id"].map(
        lambda method_id: config.method_spec(method_id)["display"]
    )
    source["causal_regret"] = source.apply(
        _mean_ci, axis=1, metric="causal_regret_per_round"
    )
    source[
        [
            "method_display_name",
            "source_label_rate_q",
            "proxy_noise_sigma",
            "causal_regret",
            "n_seeds",
            "uncertainty_unit",
        ]
    ].to_csv(tables / "tbl_app_exp4_source_label_sweep.csv", index=False)

    source_recovery = pd.read_csv(summaries / "recoverability_phase_map_summary.csv")
    source_recovery["source_labelled_normalized_recovery"] = source_recovery.apply(
        _mean_ci, axis=1, metric="source_labelled_normalized_recovery"
    )
    source_recovery[
        [
            "source_label_rate_q",
            "proxy_noise_sigma",
            "source_labelled_normalized_recovery",
            "n_seeds",
            "uncertainty_unit",
        ]
    ].to_csv(tables / "tbl_app_exp4_source_labelled_recovery.csv", index=False)

    phase = pd.read_csv(summaries / "recoverability_phase_map_summary.csv")
    phase["oracle_normalized_recovery"] = phase.apply(
        _mean_ci, axis=1, metric="oracle_normalized_recovery"
    )
    phase[
        [
            "source_label_rate_q",
            "proxy_noise_sigma",
            "oracle_normalized_recovery",
            "n_seeds",
            "uncertainty_unit",
        ]
    ].to_csv(tables / "tbl_app_exp4_phase_grid_values.csv", index=False)

    coupling = pd.read_csv(summaries / "delay_state_coupling_summary.csv")
    coupling["method_display_name"] = coupling["method_id"].map(
        lambda method_id: config.method_spec(method_id)["display"]
    )
    coupling["causal_regret"] = coupling.apply(
        _mean_ci, axis=1, metric="causal_regret_per_round"
    )
    coupling[
        [
            "method_display_name",
            "delay_state_coupling_beta",
            "causal_regret",
            "ranking_reversal_rate_mean",
            "mean_delay_mean",
            "pending_fraction_mean",
            "n_seeds",
            "uncertainty_unit",
        ]
    ].to_csv(tables / "tbl_app_exp4_delay_state_coupling.csv", index=False)

    registry = []
    for method_id, spec in config.METHOD_REGISTRY.items():
        registry.append(
            {
                "method_id": method_id,
                "method_display_name": spec["display"],
                "information_interface": spec["information_interface"],
                "reference_role": spec["reference_role"],
                "diagnostic_only": spec["diagnostic_only"],
                "deployable": spec["deployable"],
                "uses_arrival_feedback": spec["uses_arrival_feedback"],
                "uses_source_labels": spec["uses_source_labels"],
                "uses_proxy": spec["uses_proxy"],
                "description": spec["description"],
            }
        )
    pd.DataFrame(registry).to_csv(
        tables / "tbl_app_exp4_proxy_family_comparison.csv", index=False
    )

    pd.read_csv(summaries / "proxy_distortion_diagnostic_summary.csv").to_csv(
        tables / "tbl_app_exp4_proxy_distortion_diagnostic.csv", index=False
    )
    pd.read_csv(summaries / "source_binding_advantage_summary.csv").to_csv(
        tables / "tbl_app_exp4_source_binding_advantage.csv", index=False
    )
    paired_table = _paired_appendix_table(run_dir, summaries)
    paired_table.to_csv(
        tables / "tbl_app_exp4_paired_bootstrap_comparisons.csv", index=False
    )
    paired_table.to_latex(
        tables / "tbl_app_exp4_paired_bootstrap_comparisons.tex",
        index=False,
        escape=True,
        float_format="%.6f",
    )
    pd.read_csv(summaries / "metric_specification.csv").to_csv(
        tables / "tbl_app_exp4_metric_specification.csv", index=False
    )
    pd.read_csv(summaries / "full_seed_level_results.csv").to_csv(
        tables / "full_seed_level_audit.csv", index=False
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--only-paired", action="store_true")
    args = parser.parse_args()
    run(args.run_dir, only_paired=args.only_paired)


if __name__ == "__main__":
    main()

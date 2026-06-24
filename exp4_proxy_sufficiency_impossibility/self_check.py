"""Semantic, statistical, and artifact checks for the Exp4 contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import config


def add(rows: list[dict], name: str, ok: bool, detail: str) -> None:
    rows.append(
        {"check_name": name, "status": "PASSED" if ok else "FAILED", "details": detail}
    )


def image_ok(path: Path, expected: bytes) -> bool:
    return (
        path.exists()
        and path.stat().st_size > 100
        and path.read_bytes()[: len(expected)] == expected
    )


def run(run_dir: Path) -> bool:
    run_config = json.loads(
        (run_dir / "logs" / "run_config.json").read_text(encoding="utf-8")
    )
    raw = pd.read_csv(run_dir / "raw" / "seed_level_results.csv")
    seeds = run_config["seeds"]
    rows: list[dict] = []

    expected_subexperiments = {
        "proxy_distortion_diagnostic",
        "baseline_reference",
        "source_label_sweep",
        "recoverability_phase_map",
        "delay_state_coupling_diagnostic",
    }
    add(
        rows,
        "all expected subexperiments present",
        expected_subexperiments.issubset(set(raw["subexperiment_id"])),
        str(sorted(raw["subexperiment_id"].unique())),
    )
    add(
        rows,
        "shared delay paths are identical within seed and beta",
        raw.groupby(["seed", "delay_state_coupling_beta"])["mean_delay"]
        .nunique()
        .le(1)
        .all(),
        "all methods share simulator trace by seed x beta",
    )
    add(
        rows,
        "warmup is active",
        (raw["n_eval_rounds"] == int(run_config["T"]) - config.WARMUP_T).all(),
        f"n_eval_rounds={int(run_config['T']) - config.WARMUP_T}",
    )

    source = raw[raw["subexperiment_id"].eq("source_label_sweep")]
    q0 = source[
        (source["method_id"] == "proxy_label_recovery")
        & np.isclose(source["source_label_rate_q"], 0.0)
    ]
    add(
        rows,
        "q=0 recovery route receives zero exact labels",
        len(q0) > 0 and (q0["labelled_arrivals"] == 0).all(),
        f"max={q0['labelled_arrivals'].max() if len(q0) else 'NA'}",
    )
    q1_recovery = source[
        (source["method_id"] == "proxy_label_recovery")
        & np.isclose(source["source_label_rate_q"], 1.0)
    ].sort_values("seed")
    q1_reference = source[
        source["method_id"].eq("source_labelled_reference")
    ].sort_values("seed")
    same_q1_regret = len(q1_recovery) == len(q1_reference) and np.allclose(
        q1_recovery["causal_regret_per_round"],
        q1_reference["causal_regret_per_round"],
        atol=1e-12,
        rtol=0.0,
    )
    same_q1_actions = (
        len(q1_recovery) == len(q1_reference)
        and q1_recovery["action_trace_sha256"].tolist()
        == q1_reference["action_trace_sha256"].tolist()
    )
    add(
        rows,
        "q=1 proxy-label recovery equals source-labelled reference in regret",
        same_q1_regret,
        "only exact source-labelled updates remain at q=1",
    )
    add(
        rows,
        "q=1 proxy-label recovery equals source-labelled reference in action trace",
        same_q1_actions,
        "SHA-256 over complete selected-action trace for each shared seed",
    )
    min_gap = raw[
        raw["method_id"].isin(["proxy_label_recovery", "source_labelled_reference"])
    ]["min_label_arrival_gap"].dropna()
    add(
        rows,
        "exact source updates occur after their decision",
        bool((min_gap >= 1).all()),
        f"min_gap={min_gap.min() if len(min_gap) else 'NA'}",
    )

    phase = pd.read_csv(
        run_dir / "summaries" / "recoverability_phase_map_seed_level.csv"
    )
    expected_phase = len(seeds) * len(config.Q_GRID) * len(config.PROXY_SIGMAS)
    add(
        rows,
        "complete q by sigma phase grid",
        len(phase) == expected_phase,
        f"observed={len(phase)}; expected={expected_phase}",
    )
    add(
        rows,
        "oracle phase denominator is positive",
        bool((phase["oracle_normalized_recovery_denominator"] > 0.0).all()),
        f"minimum={phase['oracle_normalized_recovery_denominator'].min():.6f}",
    )
    add(
        rows,
        "source-reference phase denominator is positive",
        bool((phase["source_labelled_normalized_recovery_denominator"] > 0.0).all()),
        f"minimum={phase['source_labelled_normalized_recovery_denominator'].min():.6f}",
    )
    q1_phase = phase[np.isclose(phase["source_label_rate_q"], 1.0)].copy()
    add(
        rows,
        "q=1 source-reference-normalized recovery equals one",
        np.allclose(
            q1_phase["source_labelled_normalized_recovery"], 1.0, atol=1e-12, rtol=0.0
        ),
        "source-labelled reference is the q=1 denominator anchor",
    )
    phase_q1_raw = raw[
        (raw["subexperiment_id"].eq("recoverability_phase_map"))
        & np.isclose(raw["source_label_rate_q"], 1.0)
    ].copy()
    source_reference_raw = raw[
        (raw["subexperiment_id"].eq("source_label_sweep"))
        & raw["method_id"].eq("source_labelled_reference")
    ][["seed", "causal_regret_per_round", "action_trace_sha256"]].copy()
    phase_q1_joined = phase_q1_raw.merge(
        source_reference_raw,
        on="seed",
        how="left",
        suffixes=("_phase", "_reference"),
        validate="many_to_one",
    )
    expected_q1_phase = len(seeds) * len(config.PROXY_SIGMAS)
    phase_q1_complete = (
        len(phase_q1_joined) == expected_q1_phase
        and phase_q1_joined["action_trace_sha256_reference"].notna().all()
    )
    phase_q1_regret_equal = phase_q1_complete and np.allclose(
        phase_q1_joined["causal_regret_per_round_phase"],
        phase_q1_joined["causal_regret_per_round_reference"],
        atol=1e-12,
        rtol=0.0,
    )
    phase_q1_trace_equal = (
        phase_q1_complete
        and phase_q1_joined["action_trace_sha256_phase"]
        .eq(phase_q1_joined["action_trace_sha256_reference"])
        .all()
    )
    add(
        rows,
        "phase-grid q=1 regret equals source-labelled reference for every seed and sigma",
        phase_q1_regret_equal,
        f"observed={len(phase_q1_joined)}; expected={expected_q1_phase}",
    )
    add(
        rows,
        "phase-grid q=1 action trace equals source-labelled reference for every seed and sigma",
        phase_q1_trace_equal,
        "SHA-256 over complete selected-action traces; proxy sigma is inactive when every arrival is source-labelled",
    )
    aggregate_source = (
        Path(__file__).resolve().parent / "aggregate_results.py"
    ).read_text(encoding="utf-8")
    phase_function = aggregate_source[
        aggregate_source.index("def _phase_map") : aggregate_source.index(
            "def _source_binding_advantage"
        )
    ]
    add(
        rows,
        "phase-map raw metrics are not clipped",
        "clip(" not in phase_function,
        "raw values are retained in both normalization metrics",
    )

    proxy_rows = raw[raw["method_id"].eq("proxy_noisy_oracle_diagnostic")]
    add(
        rows,
        "noisy proxy diagnostics use simulator-emitted observations",
        proxy_rows["proxy_observation_interface"].eq("simulator_emitted").all(),
        "noisy diagnostic never accesses latent state",
    )
    add(
        rows,
        "observable history metadata records arrival feedback",
        config.METHOD_REGISTRY["observable_history_surrogate"]["uses_arrival_feedback"]
        is True,
        "registry matches policy observe interface",
    )
    add(
        rows,
        "diagnostic and reference roles are explicitly marked",
        raw.loc[raw["method_id"].eq("proxy_oracle_diagnostic"), "diagnostic_only"].all()
        and (
            ~raw.loc[raw["method_id"].eq("source_labelled_reference"), "deployable"]
        ).all(),
        "oracle is diagnostic; source-labelled route is reference",
    )

    comparisons = pd.read_csv(
        run_dir / "summaries" / "paired_bootstrap_comparisons.csv"
    )
    if run_config["mode"] == "fast":
        valid = (
            comparisons["inference_status"].eq("fast_preview_no_formal_inference").all()
            and comparisons[["ci_low", "ci_high"]].isna().all().all()
        )
        add(
            rows,
            "fast suppresses formal confidence intervals and p-values",
            bool(valid),
            "direction checks only",
        )
    else:
        valid = (
            comparisons["inference_status"]
            .eq("formal_full_paired_percentile_bootstrap_ci")
            .all()
            and comparisons[["ci_low", "ci_high"]].notna().all().all()
        )
        add(
            rows,
            "full reports paired percentile-bootstrap confidence intervals only",
            bool(valid),
            f"n_bootstrap={config.BOOTSTRAP_N}; no p-value",
        )

    for stem in [*config.PRIMARY_FIGURE_STEMS, *config.APPENDIX_FIGURE_STEMS]:
        meta_path = run_dir / "figures" / "metadata" / f"{stem}_metadata.json"
        data_path = run_dir / "figures" / "data" / f"{stem}_data.csv"
        png_path = run_dir / "figures" / "png" / f"{stem}.png"
        pdf_path = run_dir / "figures" / "pdf" / f"{stem}.pdf"
        add(
            rows,
            f"figure bundle exists: {stem}",
            image_ok(png_path, b"\x89PNG\r\n\x1a\n")
            and image_ok(pdf_path, b"%PDF")
            and meta_path.exists()
            and data_path.exists(),
            "pdf/png/data/metadata",
        )
        if data_path.exists():
            data = pd.read_csv(data_path)
            required_columns = {
                "figure_id",
                "panel_id",
                "experiment_id",
                "method_id",
                "information_interface",
                "reference_role",
                "diagnostic_only",
                "deployable",
                "metric_id",
                "x_value",
                "y_value",
                "ci_lower",
                "ci_upper",
                "uncertainty_unit",
                "n_seeds",
                "n_bootstrap",
                "run_mode",
                "paper_result",
            }
            add(
                rows,
                f"figure data contract complete: {stem}",
                required_columns.issubset(data.columns),
                "required schema columns",
            )
    primary_meta = json.loads(
        (
            run_dir
            / "figures"
            / "metadata"
            / "fig_exp4_recoverability_boundary_metadata.json"
        ).read_text(encoding="utf-8")
    )
    add(
        rows,
        "primary figure has accepted three-panel structure",
        primary_meta.get("panels")
        == [
            "proxy distortion diagnostic",
            "source-label sweep",
            "recoverability phase map",
        ],
        str(primary_meta.get("panels")),
    )
    add(
        rows,
        "phase-map display is fixed to reference scale",
        primary_meta.get("phase_map_display_vmin") == 0.0
        and primary_meta.get("phase_map_display_vmax") == 1.0
        and primary_meta.get("phase_map_metric_raw_not_clipped") is True,
        "display scale is fixed; stored metric remains raw",
    )
    appendix_meta = json.loads(
        (
            run_dir
            / "figures"
            / "metadata"
            / "fig_app_exp4_delay_state_coupling_metadata.json"
        ).read_text(encoding="utf-8")
    )
    add(
        rows,
        "coupling figure is appendix-only and uses source-binding advantage",
        appendix_meta.get("appendix_only") is True
        and appendix_meta.get("panels")
        == ["coupling mechanism diagnostic", "source-binding advantage"],
        str(appendix_meta.get("panels")),
    )

    required_summaries = [
        "proxy_distortion_diagnostic_summary.csv",
        "source_label_sweep_summary.csv",
        "recoverability_phase_map_summary.csv",
        "recoverability_phase_map_seed_level.csv",
        "delay_state_coupling_summary.csv",
        "source_binding_advantage_summary.csv",
        "delay_calibration_audit.csv",
        "paired_bootstrap_comparisons.csv",
        "metric_specification.csv",
    ]
    add(
        rows,
        "all canonical summary outputs exist",
        all(
            (run_dir / "summaries" / filename).exists()
            for filename in required_summaries
        ),
        ", ".join(required_summaries),
    )
    add(
        rows,
        "no duplicate source-labelled recovery summary is emitted",
        not (run_dir / "summaries" / "source_labelled_recovery_summary.csv").exists(),
        "recoverability_phase_map_summary.csv carries both normalization metrics",
    )

    report = pd.DataFrame(rows)
    report.to_csv(run_dir / "checks" / "exp4_self_check_report.csv", index=False)
    return bool(report["status"].eq("PASSED").all())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    ok = run(args.run_dir)
    print(f"SELF_CHECK {'PASSED' if ok else 'FAILED'}: {args.run_dir}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

from __future__ import annotations

"""Targeted, non-Cartesian Exp1 validations.

1. Geometric-delay mean robustness at target means 5, 15, and 30.
2. Systematic-misbinding horizon scaling at T=1000, 5000, and 10000.
3. Matched shared-vs-action-dependent cancellation sweep (route-map only,
   theorem-confronting diagnostic; not a new primary mechanism).

The route-map quantities reported here reuse the arrival-assigned route
diagnostic built into the primary runner; the learner horizon files keep
their existing names and semantics.
"""

from dataclasses import replace
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

import numpy as np
import pandas as pd

from config import (
    DELAY,
    EXPERIMENT_ID,
    FAST_LEARNER,
    LEARNER,
    RUN,
    STRUCTURAL,
    THEORY_SWEEP,
    config_hash,
)
from main import load_frozen_calibration
from src.artifact_io import (
    atomic_write_csv,
    atomic_write_json,
    code_lineage,
    exp1_stage_source_hashes,
    git_commit,
    hash_payload,
    refresh_output_manifest,
    utc_now,
)
from src.delay_mechanisms import (
    generate_fixed_delay,
    generate_geometric_delay,
    solve_geometric_probability,
)
from src.derived import (
    bootstrap_mean,
    build_regret_stability_utilization,
    build_regret_stability_utilization_summary,
    regret_stability_utilization,
)
from src.path_generator import SharedPathBundle
from src.runner import (
    RunMetadata,
    run_paired_learner_consequence,
    run_route_map_diagnostic,
)
from src.structural_process import (
    generate_smooth_bounded_ar1_path,
    generate_systematic_misbinding_path,
)
from src.theory_sweeps import (
    cancellation_sweep_rows,
    exact_shift_sweep_rows,
    margin_threshold_sweep_rows,
)

PROJECT_ROOT = Path(__file__).resolve().parent
STATUS_DIR = PROJECT_ROOT / "status"


def _uniform_tape(seed: int, horizon: int) -> tuple[np.ndarray, str]:
    tape = np.random.default_rng(int(seed) + 300_000).random(int(horizon))
    digest = hashlib.sha256(np.ascontiguousarray(tape).tobytes()).hexdigest()
    return tape, digest


def _bundle(seed: int, mechanism_id: str, structural, delay) -> SharedPathBundle:
    tape, tape_hash = _uniform_tape(seed, int(np.sum(structural.source_rounds >= 0)))
    payload = {
        "seed": int(seed),
        "mechanism_id": mechanism_id,
        "structural_path_hash": structural.path_hash,
        "delay_path_hash": delay.delay_path_hash,
        "learner_uniform_tape_hash": tape_hash,
    }
    bundle_hash = hash_payload(payload)
    return SharedPathBundle(
        seed=int(seed),
        mechanism_id=mechanism_id,
        structural_path=structural,
        delay_path=delay,
        learner_uniform_tape=tape,
        learner_uniform_tape_id=f"learner_uniform:{seed}:{tape_hash[:16]}",
        learner_uniform_tape_hash=tape_hash,
        bundle_id=f"targeted:{mechanism_id}:{seed}:{bundle_hash[:16]}",
        bundle_hash=bundle_hash,
    )


def _metadata(
    run_tier: str, configuration_id: str, effective_hash: str, calibration_hash: str
) -> RunMetadata:
    return RunMetadata(
        run_id=f"{EXPERIMENT_ID}:targeted:{run_tier}:{configuration_id}:{utc_now()}",
        run_tier=run_tier,
        paper_result=False,
        analysis_tier="targeted",
        configuration_id=configuration_id,
        code_commit=git_commit(PROJECT_ROOT),
        config_hash=effective_hash,
        input_manifest_hash=calibration_hash,
        calibration_manifest_hash=calibration_hash,
        generated_at=utc_now(),
    )


def _summarize_mean_delay(seed_metrics: pd.DataFrame, repetitions: int) -> pd.DataFrame:
    rows = []
    for (target, binding), group in seed_metrics.groupby(
        ["target_mean_delay", "feedback_binding_id"], sort=True
    ):
        summary = bootstrap_mean(
            group.structural_regret_rate,
            repetitions,
            RUN.ci_level,
            ("targeted_mean_delay", float(target), binding),
        )
        delay_summary = bootstrap_mean(
            group.generated_mean_delay,
            repetitions,
            RUN.ci_level,
            ("targeted_generated_delay", float(target), binding),
        )
        rows.append(
            {
                "targeted_component": "mean_delay_robustness",
                "target_mean_delay": float(target),
                "feedback_binding_id": binding,
                "metric_id": "structural_regret_rate",
                **summary,
                "generated_mean_delay": delay_summary["estimate"],
                "generated_mean_delay_ci_lower": delay_summary["ci_lower"],
                "generated_mean_delay_ci_upper": delay_summary["ci_upper"],
                "bootstrap_repetitions": repetitions,
                "ci_level": RUN.ci_level,
                "paper_result": False,
            }
        )
    return pd.DataFrame(rows)


def _summarize_horizon(seed_metrics: pd.DataFrame, repetitions: int) -> pd.DataFrame:
    rows = []
    for (horizon, binding), group in seed_metrics.groupby(
        ["target_horizon", "feedback_binding_id"], sort=True
    ):
        for metric in ("structural_regret", "structural_regret_rate"):
            summary = bootstrap_mean(
                group[metric],
                repetitions,
                RUN.ci_level,
                ("targeted_horizon", int(horizon), binding, metric),
            )
            rows.append(
                {
                    "targeted_component": "horizon_scaling",
                    "target_horizon": int(horizon),
                    "feedback_binding_id": binding,
                    "metric_id": metric,
                    **summary,
                "bootstrap_repetitions": repetitions,
                "ci_level": RUN.ci_level,
                "paper_result": False,
            }
        )
    return pd.DataFrame(rows)


def _attach_utilization_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Add realized stability-utilization columns to route seed-metric rows."""
    utilization: list[float] = []
    defined: list[bool] = []
    tolerance: list[float] = []
    for record in frame.to_dict("records"):
        value, is_defined, budget_tolerance = regret_stability_utilization(
            record["structural_regret"],
            record["route_regret"],
            record["alignment_budget"],
            int(record["n_rounds"]),
        )
        utilization.append(value)
        defined.append(bool(is_defined))
        tolerance.append(budget_tolerance)
    out = frame.copy()
    out["alignment_budget_tolerance"] = tolerance
    out["regret_stability_utilization"] = utilization
    out["utilization_defined"] = defined
    return out


def _summarize_horizon_route(
    seed_metrics: pd.DataFrame, repetitions: int
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    metrics = (
        "structural_regret",
        "route_regret",
        "alignment_budget",
        "structural_regret_rate",
        "route_regret_rate",
        "alignment_budget_rate",
        "complete_conflict_rate",
        "regret_stability_slack_rate",
    )
    for (horizon, route), group in seed_metrics.groupby(
        ["target_horizon", "route_id"], sort=True
    ):
        manuscript_facing = bool(route == "arrival_assigned")
        for metric in metrics:
            summary = bootstrap_mean(
                group[metric],
                repetitions,
                RUN.ci_level,
                ("targeted_horizon_route", int(horizon), route, metric),
            )
            rows.append(
                {
                    "targeted_component": "horizon_route_map",
                    "target_horizon": int(horizon),
                    "route_id": route,
                    "manuscript_facing": manuscript_facing,
                    "metric_id": metric,
                    **summary,
                    "bootstrap_repetitions": repetitions,
                    "ci_level": RUN.ci_level,
                    "paper_result": False,
                }
            )
        defined = group[group["utilization_defined"].astype(bool)]
        utilization = bootstrap_mean(
            defined["regret_stability_utilization"],
            repetitions,
            RUN.ci_level,
            ("targeted_horizon_route_utilization", int(horizon), route),
        )
        rows.append(
            {
                "targeted_component": "horizon_route_map",
                "target_horizon": int(horizon),
                "route_id": route,
                "manuscript_facing": manuscript_facing,
                "metric_id": "regret_stability_utilization",
                "n_total_seeds": int(group["seed"].nunique()),
                "n_defined": int(defined["seed"].nunique()),
                **utilization,
                "bootstrap_repetitions": repetitions,
                "ci_level": RUN.ci_level,
                "paper_result": False,
            }
        )
    return pd.DataFrame(rows)


def _summarize_cancellation(
    rows: list[dict[str, Any]], repetitions: int
) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    summaries: list[dict[str, Any]] = []
    metrics = (
        "mean_absolute_actionwise_level_error",
        "mean_delta",
        "alignment_budget_rate",
        "mean_rho",
        "mean_chi",
        "complete_conflict_rate",
        "regret_map_linf_to_structural",
    )
    for (profile, scale, ratio), group in frame.groupby(
        ["shared_profile", "alpha_shared", "alpha_dep"], sort=True
    ):
        for metric in metrics:
            summary = bootstrap_mean(
                group[metric],
                repetitions,
                RUN.ci_level,
                ("cancellation", profile, float(scale), float(ratio), metric),
            )
            summaries.append(
                {
                    "cancellation_sweep_id": "cancellation_shared_vs_action_dependent",
                    "shared_profile": profile,
                    "alpha_shared": float(scale),
                    "alpha_dep": float(ratio),
                    "metric_id": metric,
                    **summary,
                    "bootstrap_repetitions": repetitions,
                    "ci_level": RUN.ci_level,
                    "paper_result": False,
                }
            )
    return pd.DataFrame(summaries)


def execute(run_tier: str, force: bool = False) -> Path:
    if run_tier not in ("fast", "full"):
        raise ValueError("run_tier must be fast or full")
    prerequisite = STATUS_DIR / f"{run_tier}_validation_status.json"
    if not prerequisite.exists():
        raise RuntimeError(f"Targeted run requires validated {run_tier} primary output")
    prerequisite_payload = json.loads(prerequisite.read_text(encoding="utf-8"))
    if (
        prerequisite_payload.get("engineering_status") != "PASS"
        or prerequisite_payload.get("scientific_status") != "PASS"
    ):
        raise RuntimeError("Targeted run prerequisite is not PASS")

    calibration = load_frozen_calibration()
    selected = calibration["structural"]["selected_value"]
    seeds = RUN.fast_seeds if run_tier == "fast" else RUN.evaluation_seeds
    repetitions = (
        RUN.bootstrap_repetitions_fast
        if run_tier == "fast"
        else RUN.bootstrap_repetitions_full
    )
    learner_mean = FAST_LEARNER if run_tier == "fast" else LEARNER
    mean_horizon = 500 if run_tier == "fast" else 5000
    base_structural = replace(
        STRUCTURAL,
        horizon=mean_horizon,
        ar_coefficient=float(selected["ar_coefficient"]),
        innovation_sd=float(selected["innovation_sd"]),
    )
    effective_hash = config_hash(structural=base_structural, learner=learner_mean)
    calibration_hash = hash_payload(calibration["manifest"])

    output = PROJECT_ROOT / "outputs" / run_tier / "targeted"
    if output.exists():
        if not force:
            raise FileExistsError(f"Targeted output exists: {output}")
        shutil.rmtree(output)
    output.mkdir(parents=True)

    mean_rows = []
    for target_mean in (5.0, 15.0, 30.0):
        probability = solve_geometric_probability(target_mean, DELAY.d_max)
        for seed in seeds:
            structural = generate_smooth_bounded_ar1_path(base_structural, int(seed))
            delay = generate_geometric_delay(structural, probability, DELAY.d_max)
            bundle = _bundle(int(seed), "geometric_delay", structural, delay)
            metadata = _metadata(
                run_tier,
                f"targeted_geometric_mean_{target_mean:g}",
                effective_hash,
                calibration_hash,
            )
            _, seed_frame = run_paired_learner_consequence(
                bundle,
                metadata,
                learner_mean,
                calibration["context"],
            )
            seed_frame["targeted_component"] = "mean_delay_robustness"
            seed_frame["target_mean_delay"] = target_mean
            seed_frame["generated_mean_delay"] = delay.generated_mean_delay
            mean_rows.append(seed_frame)
    mean_seed = pd.concat(mean_rows, ignore_index=True)

    horizon_rows = []
    horizon_route_rows: list[pd.DataFrame] = []
    prefix_checks = []
    block_length = int(calibration["misbinding"]["selected_block_length"])
    horizon_learner = LEARNER  # Frozen at primary T=5000 for all scaling cells.
    for seed in seeds:
        reference_state = None
        reference_tape = None
        for horizon in (1000, 5000, 10000):
            structural_config = replace(
                STRUCTURAL,
                horizon=horizon,
                ar_coefficient=float(selected["ar_coefficient"]),
                innovation_sd=float(selected["innovation_sd"]),
            )
            structural = generate_systematic_misbinding_path(
                structural_config,
                int(seed),
                block_length=block_length,
            )
            delay = generate_fixed_delay(structural, DELAY.fixed_delay)
            bundle = _bundle(int(seed), "systematic_misbinding", structural, delay)
            if reference_state is None:
                reference_state = structural.structural_state[
                    structural.source_rounds >= 0
                ].copy()
                reference_tape = bundle.learner_uniform_tape.copy()
            else:
                n = min(reference_state.size, horizon)
                prefix_checks.append(
                    bool(
                        np.array_equal(
                            structural.structural_state[structural.source_rounds >= 0][
                                :n
                            ],
                            reference_state[:n],
                        )
                        and np.array_equal(
                            bundle.learner_uniform_tape[:n], reference_tape[:n]
                        )
                    )
                )
                if horizon > reference_state.size:
                    reference_state = structural.structural_state[
                        structural.source_rounds >= 0
                    ].copy()
                    reference_tape = bundle.learner_uniform_tape.copy()
            metadata = _metadata(
                run_tier,
                f"targeted_systematic_horizon_{horizon}",
                config_hash(structural=structural_config, learner=horizon_learner),
                calibration_hash,
            )
            _, seed_frame = run_paired_learner_consequence(
                bundle,
                metadata,
                horizon_learner,
                calibration["context"],
            )
            seed_frame["targeted_component"] = "horizon_scaling"
            seed_frame["target_horizon"] = horizon
            horizon_rows.append(seed_frame)
            # Route-map diagnostic on the SAME bundle and metadata: no second
            # independently generated path is created.
            _, route_seed_frame = run_route_map_diagnostic(bundle, metadata)
            route_seed_frame["targeted_component"] = "horizon_route_map"
            route_seed_frame["target_horizon"] = horizon
            horizon_route_rows.append(route_seed_frame)
    if prefix_checks and not all(prefix_checks):
        raise RuntimeError("Horizon-scaling shared-prefix invariant failed")
    horizon_seed = pd.concat(horizon_rows, ignore_index=True)
    if not horizon_route_rows:
        raise RuntimeError("Horizon route-map diagnostic produced no rows")
    horizon_route_seed = _attach_utilization_columns(
        pd.concat(horizon_route_rows, ignore_index=True)
    )
    if not bool(horizon_route_seed.regret_stability_invariant_pass.all()):
        raise RuntimeError("Horizon route-map stability inequality failed")
    if not bool(horizon_route_seed.utilization_defined.any()):
        raise RuntimeError("Horizon route-map stability utilization is undefined")

    # --- Theory-targeted controlled sweeps (config v1.2). -----------------
    # These are theorem diagnostics, not new delay mechanisms. They reuse the
    # calibrated structural configuration and the frozen geometric delay path
    # construction, and are integrated through this non-Cartesian validation
    # layer only.
    geometric_probability = float(calibration["delay"]["geometric_probability"])
    exact_rows, exact_checks = exact_shift_sweep_rows(
        base_structural,
        seeds,
        geometric_probability,
        DELAY,
        scales=THEORY_SWEEP.exact_shift_scales,
    )
    margin_rows, margin_checks = margin_threshold_sweep_rows(
        base_structural,
        seeds,
        ratios=THEORY_SWEEP.margin_distortion_ratios,
    )
    # Matched shared-vs-action-dependent cancellation sweep. Route-map only:
    # the learner is never called and no primary artifact is written.
    cancellation_rows, cancellation_checks = cancellation_sweep_rows(
        base_structural,
        seeds,
        shared_scales=THEORY_SWEEP.cancellation_shared_scales,
        dep_ratios=THEORY_SWEEP.cancellation_dep_ratios,
        shared_profiles=THEORY_SWEEP.cancellation_shared_profiles,
    )
    exact_frame = pd.DataFrame(exact_rows)
    margin_frame = pd.DataFrame(margin_rows)
    cancellation_frame = pd.DataFrame(cancellation_rows)

    mean_summary = _summarize_mean_delay(mean_seed, repetitions)
    horizon_summary = _summarize_horizon(horizon_seed, repetitions)
    horizon_route_summary = _summarize_horizon_route(horizon_route_seed, repetitions)
    cancellation_summary = _summarize_cancellation(cancellation_rows, repetitions)
    utilization_defined_rows = int(horizon_route_seed.utilization_defined.sum())
    overall_status = (
        "PASS"
        if exact_checks["passed"]
        and margin_checks["passed"]
        and cancellation_checks["passed"]
        else "FAIL"
    )
    atomic_write_csv(output / "exp1_targeted_mean_delay_seed_metrics.csv", mean_seed)
    atomic_write_csv(output / "exp1_targeted_horizon_seed_metrics.csv", horizon_seed)
    atomic_write_csv(
        output / "exp1_targeted_horizon_route_seed_metrics.csv", horizon_route_seed
    )
    atomic_write_csv(output / "exp1_targeted_mean_delay_summary.csv", mean_summary)
    atomic_write_csv(output / "exp1_targeted_horizon_summary.csv", horizon_summary)
    atomic_write_csv(
        output / "exp1_targeted_horizon_route_summary.csv", horizon_route_summary
    )
    atomic_write_csv(output / "exp1_targeted_theory_exact_shift_sweep.csv", exact_frame)
    atomic_write_csv(
        output / "exp1_targeted_theory_margin_threshold_sweep.csv", margin_frame
    )
    atomic_write_csv(
        output / "exp1_targeted_cancellation_sweep.csv", cancellation_frame
    )
    atomic_write_csv(
        output / "exp1_targeted_cancellation_summary.csv", cancellation_summary
    )
    atomic_write_csv(
        output / "fig_exp1_targeted_validation_data.csv",
        pd.concat([mean_summary, horizon_summary], ignore_index=True, sort=False),
    )
    atomic_write_json(
        output / "exp1_targeted_validation_report.json",
        {
            "experiment_id": EXPERIMENT_ID,
            "run_tier": run_tier,
            "analysis_tier": "targeted",
            "paper_result": False,
            "mean_delay_levels": [5, 15, 30],
            "horizon_levels": [1000, 5000, 10000],
            "horizon_shared_prefix_pass": (
                bool(all(prefix_checks)) if prefix_checks else True
            ),
            "horizon_route_map": {
                "levels": [1000, 5000, 10000],
                "manuscript_facing_route": "arrival_assigned",
                "stability_inequality_pass": bool(
                    horizon_route_seed.regret_stability_invariant_pass.all()
                ),
                "utilization_defined_rows": utilization_defined_rows,
                "seed_metrics": "targeted/exp1_targeted_horizon_route_seed_metrics.csv",
                "summary": "targeted/exp1_targeted_horizon_route_summary.csv",
                "paper_result": False,
            },
            "theory_exact_cardinal_shift_sweep": exact_checks,
            "theory_margin_threshold_sweep": margin_checks,
            "cancellation_sweep": {
                "sweep_id": cancellation_checks["sweep_id"],
                "grid_cells_per_seed": cancellation_checks["grid_cells_per_seed"],
                "seeds": [int(seed) for seed in seeds],
                "n_cells": cancellation_checks["n_cells"],
                "tolerance": cancellation_checks["tolerance"],
                "max_numerical_deviation": cancellation_checks[
                    "max_numerical_deviation"
                ],
                "gates": {
                    name: cancellation_checks[name]["passed"]
                    for name in (
                        "C1_pure_shared",
                        "C2_shared_amplitude_invariance",
                        "C3_profile_invariance",
                        "C4_delta_margin_ratio",
                        "C5_choice_threshold",
                        "C6_no_clipping_no_learner",
                    )
                },
                "sweep": "targeted/exp1_targeted_cancellation_sweep.csv",
                "summary": "targeted/exp1_targeted_cancellation_summary.csv",
                "invariants": "targeted/exp1_targeted_cancellation_invariants.json",
                "paper_result": False,
            },
            "status": overall_status,
            "code_lineage": code_lineage(PROJECT_ROOT),
            "validation_source_hash": exp1_stage_source_hashes(PROJECT_ROOT)[
                "validation_source_hash"
            ],
            "generated_at": utc_now(),
        },
    )
    atomic_write_json(
        output / "exp1_targeted_cancellation_invariants.json",
        {
            "experiment_id": EXPERIMENT_ID,
            "run_tier": run_tier,
            "analysis_tier": "targeted",
            "paper_result": False,
            "horizon_levels": [1000, 5000, 10000],
            "cancellation_sweep": cancellation_checks,
            "status": (
                "PASS" if cancellation_checks["passed"] else "FAIL"
            ),
            "validation_source_hash": exp1_stage_source_hashes(PROJECT_ROOT)[
                "validation_source_hash"
            ],
            "generated_at": utc_now(),
        },
    )
    atomic_write_json(
        STATUS_DIR / f"{run_tier}_targeted_status.json",
        {
            "stage": f"{run_tier}_targeted",
            "status": overall_status,
            "paper_result": False,
            "code_lineage": code_lineage(PROJECT_ROOT),
            "validation_source_hash": exp1_stage_source_hashes(PROJECT_ROOT)[
                "validation_source_hash"
            ],
            "output": f"outputs/{run_tier}/targeted",
            "generated_at": utc_now(),
        },
    )
    refresh_output_manifest(PROJECT_ROOT / "outputs" / run_tier)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_tier", nargs="?", choices=("fast", "full"))
    parser.add_argument("--run", dest="run_option", choices=("fast", "full"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run_tier = args.run_option or args.run_tier
    if run_tier is None:
        parser.error("provide run tier positionally or with --run")
    output = execute(run_tier, force=args.force)
    print("TARGETED_VALIDATION_COMPLETE")
    print("paper_result=false")
    print(f"output={output}")


if __name__ == "__main__":
    main()

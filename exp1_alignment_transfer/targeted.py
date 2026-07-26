from __future__ import annotations

"""Targeted, non-Cartesian Exp1 validations.

1. Geometric-delay mean robustness at target means 5, 15, and 30.
2. Systematic-misbinding horizon scaling at T=1000, 5000, and 10000.
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

from config import DELAY, EXPERIMENT_ID, FAST_LEARNER, LEARNER, RUN, STRUCTURAL, config_hash
from main import load_frozen_calibration
from src.artifact_io import atomic_write_csv, atomic_write_json, code_lineage, git_commit, hash_payload, refresh_output_manifest, utc_now
from src.delay_mechanisms import generate_fixed_delay, generate_geometric_delay, solve_geometric_probability
from src.derived import bootstrap_mean
from src.path_generator import SharedPathBundle
from src.runner import RunMetadata, run_paired_learner_consequence
from src.structural_process import generate_smooth_bounded_ar1_path, generate_systematic_misbinding_path


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


def _metadata(run_tier: str, configuration_id: str, effective_hash: str, calibration_hash: str) -> RunMetadata:
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


def execute(run_tier: str, force: bool = False) -> Path:
    if run_tier not in ("fast", "full"):
        raise ValueError("run_tier must be fast or full")
    prerequisite = STATUS_DIR / f"{run_tier}_validation_status.json"
    if not prerequisite.exists():
        raise RuntimeError(f"Targeted run requires validated {run_tier} primary output")
    prerequisite_payload = json.loads(prerequisite.read_text(encoding="utf-8"))
    if prerequisite_payload.get("engineering_status") != "PASS" or prerequisite_payload.get("scientific_status") != "PASS":
        raise RuntimeError("Targeted run prerequisite is not PASS")

    calibration = load_frozen_calibration()
    selected = calibration["structural"]["selected_value"]
    seeds = RUN.fast_seeds if run_tier == "fast" else RUN.evaluation_seeds
    repetitions = RUN.bootstrap_repetitions_fast if run_tier == "fast" else RUN.bootstrap_repetitions_full
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
                reference_state = structural.structural_state[structural.source_rounds >= 0].copy()
                reference_tape = bundle.learner_uniform_tape.copy()
            else:
                n = min(reference_state.size, horizon)
                prefix_checks.append(
                    bool(
                        np.array_equal(
                            structural.structural_state[structural.source_rounds >= 0][:n],
                            reference_state[:n],
                        )
                        and np.array_equal(bundle.learner_uniform_tape[:n], reference_tape[:n])
                    )
                )
                if horizon > reference_state.size:
                    reference_state = structural.structural_state[structural.source_rounds >= 0].copy()
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
    if prefix_checks and not all(prefix_checks):
        raise RuntimeError("Horizon-scaling shared-prefix invariant failed")
    horizon_seed = pd.concat(horizon_rows, ignore_index=True)

    mean_summary = _summarize_mean_delay(mean_seed, repetitions)
    horizon_summary = _summarize_horizon(horizon_seed, repetitions)
    atomic_write_csv(output / "exp1_targeted_mean_delay_seed_metrics.csv", mean_seed)
    atomic_write_csv(output / "exp1_targeted_horizon_seed_metrics.csv", horizon_seed)
    atomic_write_csv(output / "exp1_targeted_mean_delay_summary.csv", mean_summary)
    atomic_write_csv(output / "exp1_targeted_horizon_summary.csv", horizon_summary)
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
            "horizon_shared_prefix_pass": bool(all(prefix_checks)) if prefix_checks else True,
            "status": "PASS",
            "code_lineage": code_lineage(PROJECT_ROOT),
            "generated_at": utc_now(),
        },
    )
    atomic_write_json(
        STATUS_DIR / f"{run_tier}_targeted_status.json",
        {
            "stage": f"{run_tier}_targeted",
            "status": "PASS",
            "paper_result": False,
            "code_lineage": code_lineage(PROJECT_ROOT),
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

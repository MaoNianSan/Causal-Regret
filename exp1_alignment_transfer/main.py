from __future__ import annotations

"""Primary execution entry point for Experiment 1."""

from dataclasses import asdict, replace
import argparse
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
    FAST_STRUCTURAL,
    LEARNER,
    MECHANISM_ORDER,
    RUN,
    STRUCTURAL,
    config_hash,
)
from src.artifact_io import (
    atomic_write_csv,
    atomic_write_json,
    atomic_write_parquet,
    code_lineage,
    git_commit,
    hash_payload,
    utc_now,
    ParquetStreamWriter,
    read_frame,
    refresh_output_manifest,
)
from src.contracts import (
    CalibrationError,
    LEARNER_ROUND_COLUMNS,
    ROUTE_ROUND_COLUMNS,
)
from src.derived import generate_all_derived
from src.path_generator import build_shared_path_bundle
from src.runner import RunMetadata, run_paired_learner_consequence, run_route_map_diagnostic


PROJECT_ROOT = Path(__file__).resolve().parent
CALIBRATION_DIR = PROJECT_ROOT / "calibration"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
STATUS_DIR = PROJECT_ROOT / "status"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CalibrationError(f"Required frozen calibration artifact is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_frozen_calibration() -> dict[str, Any]:
    manifest = _load_json(CALIBRATION_DIR / "exp1_calibration_manifest.json")
    if manifest.get("calibration_status") != "PASS":
        raise CalibrationError("Calibration manifest is not PASS")
    structural = _load_json(CALIBRATION_DIR / "exp1_structural_calibration.json")
    delay = _load_json(CALIBRATION_DIR / "exp1_delay_calibration.json")
    misbinding = _load_json(CALIBRATION_DIR / "exp1_misbinding_calibration.json")
    context = _load_json(CALIBRATION_DIR / "exp1_context_partition.json")
    if any(payload.get("evaluation_seed_overlap") for payload in (structural, delay, misbinding, context)):
        raise CalibrationError("Calibration and evaluation seeds overlap")
    payloads = {"structural": structural, "delay": delay, "misbinding": misbinding, "context": context}
    expected_hashes = manifest.get("artifact_hashes", {})
    actual_hashes = {key: hash_payload(payload) for key, payload in payloads.items()}
    if expected_hashes != actual_hashes:
        raise CalibrationError(
            f"Calibration artifact hash mismatch: expected={expected_hashes}, actual={actual_hashes}"
        )
    current_lineage = code_lineage(PROJECT_ROOT)
    if manifest.get("code_lineage") != current_lineage:
        raise CalibrationError(
            "Calibration was generated from a different code lineage. "
            f"manifest={manifest.get('code_lineage')}, current={current_lineage}. "
            "Run calibrate.py --force only after an approved change memo."
        )
    return {
        "manifest": manifest,
        "structural": structural,
        "delay": delay,
        "misbinding": misbinding,
        "context": context,
    }


def _prepare_output(output_root: Path, force: bool) -> None:
    if output_root.exists():
        if not force:
            raise FileExistsError(
                f"Output directory already exists: {output_root}. Use --force only after review."
            )
        shutil.rmtree(output_root)
    for relative in (
        "raw",
        "seed_metrics",
        "derived",
        "figures/data",
        "figures/png",
        "figures/pdf",
        "figures/metadata",
        "tables",
        "manuscript",
        "checks",
        "metadata",
    ):
        (output_root / relative).mkdir(parents=True, exist_ok=True)


def _path_manifest_row(bundle, metadata: RunMetadata, structural_config) -> dict[str, Any]:
    delay = bundle.delay_path.delays
    arrivals = bundle.delay_path.arrival_clocks
    eval_mask = bundle.delay_path.source_rounds >= 0
    eval_delays = delay[eval_mask]
    eval_arrivals = arrivals[eval_mask]
    observed = eval_arrivals < structural_config.horizon
    terminal_unobserved = int(np.sum(~observed))
    clocks = np.arange(structural_config.horizon)
    all_arrivals = arrivals[(arrivals >= 0) & (arrivals < structural_config.horizon)]
    batch_counts = np.bincount(all_arrivals.astype(int), minlength=structural_config.horizon)
    losses = bundle.structural_path.structural_loss_matrix
    return {
        "run_id": metadata.run_id,
        "run_tier": metadata.run_tier,
        "paper_result": metadata.paper_result,
        "analysis_tier": metadata.analysis_tier,
        "experiment_id": EXPERIMENT_ID,
        "configuration_id": metadata.configuration_id,
        "seed": bundle.seed,
        "mechanism_id": bundle.mechanism_id,
        "structural_family_id": bundle.structural_path.structural_family_id,
        "horizon": structural_config.horizon,
        "prehistory_length": structural_config.prehistory_length,
        "state_burn_in": structural_config.state_burn_in,
        "k_actions": structural_config.k_actions,
        "d_max": DELAY.d_max,
        "structural_path_id": bundle.structural_path.path_id,
        "structural_path_hash": bundle.structural_path.path_hash,
        "delay_path_id": bundle.delay_path.delay_path_id,
        "delay_path_hash": bundle.delay_path.delay_path_hash,
        "learner_uniform_tape_id": bundle.learner_uniform_tape_id,
        "learner_uniform_tape_hash": bundle.learner_uniform_tape_hash,
        "bundle_id": bundle.bundle_id,
        "bundle_hash": bundle.bundle_hash,
        "generated_mean_delay": float(np.mean(eval_delays)),
        "observed_mean_delay": float(np.mean(eval_delays[observed])) if np.any(observed) else float("nan"),
        "right_censoring_rate": float(np.mean(~observed)),
        "empty_arrival_clock_rate": float(np.mean(batch_counts == 0)),
        "multiarrival_clock_rate": float(np.mean(batch_counts > 1)),
        "max_arrival_batch_size": int(np.max(batch_counts)),
        "structural_loss_min": float(np.min(losses)),
        "structural_loss_max": float(np.max(losses)),
        "loss_clipping_count": 0,
        "learner_prehistory_policy": "cold_start_empty_queue",
        "delay_sd": float(np.std(delay)),
        "delay_q50": float(np.quantile(delay, 0.50)),
        "delay_q90": float(np.quantile(delay, 0.90)),
        "delay_q99": float(np.quantile(delay, 0.99)),
        "terminal_unobserved_source_events": terminal_unobserved,
        "arrival_batch_aggregation": DELAY.batch_aggregation,
        "empty_arrival_rule": DELAY.empty_clock_rule,
        "delay_parameter_payload": bundle.delay_path.delay_parameter_payload,
        "structural_parameter_payload": bundle.structural_path.parameter_payload,
        "code_commit": metadata.code_commit,
        "config_hash": metadata.config_hash,
        "input_manifest_hash": metadata.input_manifest_hash,
        "calibration_manifest_hash": metadata.calibration_manifest_hash,
        "generated_at": metadata.generated_at,
    }


def execute(run_tier: str, force: bool = False) -> Path:
    if run_tier not in ("fast", "full"):
        raise ValueError("run_tier must be 'fast' or 'full'")
    calibration = load_frozen_calibration()
    calibration_status_path = STATUS_DIR / "calibration_status.json"
    if not calibration_status_path.exists() or json.loads(calibration_status_path.read_text(encoding="utf-8")).get("status") != "PASS":
        raise CalibrationError("Calibration stage status is not PASS")
    if run_tier == "full":
        fast_validation = STATUS_DIR / "fast_validation_status.json"
        if not fast_validation.exists():
            raise RuntimeError("Full run is blocked until fast validation status exists")
        fast_payload = json.loads(fast_validation.read_text(encoding="utf-8"))
        if fast_payload.get("engineering_status") != "PASS" or fast_payload.get("scientific_status") != "PASS":
            raise RuntimeError("Full run is blocked because fast engineering/scientific status is not PASS")
        if fast_payload.get("code_lineage") != code_lineage(PROJECT_ROOT):
            raise RuntimeError("Full run is blocked because fast validation used a different package-local code lineage")
        if fast_payload.get("calibration_manifest_hash") != hash_payload(calibration["manifest"]):
            raise RuntimeError("Full run is blocked because fast validation used a different calibration manifest")
    selected = calibration["structural"]["selected_value"]
    base_structural = FAST_STRUCTURAL if run_tier == "fast" else STRUCTURAL
    structural_config = replace(
        base_structural,
        ar_coefficient=float(selected["ar_coefficient"]),
        innovation_sd=float(selected["innovation_sd"]),
    )
    learner_config = FAST_LEARNER if run_tier == "fast" else LEARNER
    # Recompute because selected structural parameters are part of the effective config.
    effective_hash = config_hash(structural=structural_config, learner=learner_config)
    seeds = RUN.fast_seeds if run_tier == "fast" else RUN.evaluation_seeds
    bootstrap_repetitions = (
        RUN.bootstrap_repetitions_fast
        if run_tier == "fast"
        else RUN.bootstrap_repetitions_full
    )
    output_root = OUTPUTS_DIR / run_tier
    _prepare_output(output_root, force=force)

    code_commit = git_commit(PROJECT_ROOT)
    lineage = code_lineage(PROJECT_ROOT)
    calibration_hash = hash_payload(calibration["manifest"])
    run_id = f"{EXPERIMENT_ID}:{run_tier}:{utc_now()}"
    metadata = RunMetadata(
        run_id=run_id,
        run_tier=run_tier,
        paper_result=False,
        analysis_tier="primary",
        configuration_id=f"primary_t{structural_config.horizon}_k{structural_config.k_actions}",
        code_commit=code_commit,
        config_hash=effective_hash,
        input_manifest_hash=calibration_hash,
        calibration_manifest_hash=calibration_hash,
        generated_at=utc_now(),
    )
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        STATUS_DIR / f"{run_tier}_run_status.json",
        {
            "stage": f"{run_tier}_run",
            "status": "RUNNING",
            "paper_result": False,
            "started_at": utc_now(),
        },
    )
    atomic_write_json(
        output_root / "metadata" / "run_state.json",
        {
            "run_id": run_id,
            "run_tier": run_tier,
            "status": "RUNNING",
            "paper_result": False,
            "started_at": utc_now(),
            "code_commit": code_commit,
            "code_lineage": lineage,
            "effective_structural_config": asdict(structural_config),
            "effective_learner_config": asdict(learner_config),
            "seeds": list(seeds),
            "mechanisms": list(MECHANISM_ORDER),
            "bootstrap_repetitions": bootstrap_repetitions,
            "config_hash": effective_hash,
            "calibration_manifest_hash": calibration_hash,
        },
    )

    path_rows = []
    route_seed_frames = []
    learner_seed_frames = []
    route_writer = ParquetStreamWriter(output_root / "raw" / "exp1_route_diagnostic_rounds.parquet")
    learner_writer = ParquetStreamWriter(output_root / "raw" / "exp1_learner_consequence_rounds.parquet")
    delay_writer = ParquetStreamWriter(output_root / "raw" / "exp1_delay_source_rounds.parquet")

    try:
        for seed in seeds:
            for mechanism_id in MECHANISM_ORDER:
                bundle = build_shared_path_bundle(
                    seed=int(seed),
                    mechanism_id=mechanism_id,
                    frozen_calibration=calibration,
                    structural_config=structural_config,
                    delay_config=DELAY,
                )
                path_rows.append(_path_manifest_row(bundle, metadata, structural_config))
                delay_frame = pd.DataFrame(
                        {
                            "run_id": metadata.run_id,
                            "run_tier": metadata.run_tier,
                            "paper_result": metadata.paper_result,
                            "analysis_tier": metadata.analysis_tier,
                            "experiment_id": EXPERIMENT_ID,
                            "configuration_id": metadata.configuration_id,
                            "seed": bundle.seed,
                            "mechanism_id": bundle.mechanism_id,
                            "source_round": bundle.delay_path.source_rounds,
                            "delay": bundle.delay_path.delays,
                            "arrival_clock": bundle.delay_path.arrival_clocks,
                            "structural_state": bundle.structural_path.structural_state,
                            "is_evaluation_source": bundle.delay_path.source_rounds >= 0,
                            "structural_path_hash": bundle.structural_path.path_hash,
                            "delay_path_hash": bundle.delay_path.delay_path_hash,
                            "code_commit": metadata.code_commit,
                            "config_hash": metadata.config_hash,
                            "input_manifest_hash": metadata.input_manifest_hash,
                            "calibration_manifest_hash": metadata.calibration_manifest_hash,
                            "generated_at": metadata.generated_at,
                        }
                    )
                route_round, route_seed = run_route_map_diagnostic(bundle, metadata)
                learner_round, learner_seed = run_paired_learner_consequence(
                    bundle,
                    metadata,
                    learner_config=learner_config,
                    context_partition=calibration["context"],
                )
                missing_route = [column for column in ROUTE_ROUND_COLUMNS if column not in route_round.columns]
                missing_learner = [column for column in LEARNER_ROUND_COLUMNS if column not in learner_round.columns]
                if missing_route or missing_learner:
                    raise RuntimeError(
                        f"Schema construction failed: route missing={missing_route}, learner missing={missing_learner}"
                    )
                route_writer.write(route_round)
                learner_writer.write(learner_round)
                delay_writer.write(delay_frame)
                route_seed_frames.append(route_seed)
                learner_seed_frames.append(learner_seed)
        route_writer.close()
        learner_writer.close()
        delay_writer.close()
    except Exception:
        route_writer.abort()
        learner_writer.abort()
        delay_writer.abort()
        raise

    path_manifest = pd.DataFrame(path_rows)
    route_seed = pd.concat(route_seed_frames, ignore_index=True)
    learner_seed = pd.concat(learner_seed_frames, ignore_index=True)

    atomic_write_parquet(output_root / "raw" / "exp1_path_manifest.parquet", path_manifest)
    atomic_write_parquet(
        output_root / "seed_metrics" / "exp1_route_seed_metrics.parquet", route_seed
    )
    atomic_write_parquet(
        output_root / "seed_metrics" / "exp1_learner_seed_metrics.parquet", learner_seed
    )
    # CSV copies are intentional review artifacts, not parquet fallbacks.
    atomic_write_csv(output_root / "seed_metrics" / "exp1_route_seed_metrics.csv", route_seed)
    atomic_write_csv(output_root / "seed_metrics" / "exp1_learner_seed_metrics.csv", learner_seed)

    delay_round = read_frame(output_root / "raw" / "exp1_delay_source_rounds.parquet")
    route_path = output_root / "raw" / "exp1_route_diagnostic_rounds.parquet"
    if route_path.exists():
        route_round = pd.read_parquet(
            route_path,
            filters=[
                ("route_id", "==", "arrival_assigned"),
                ("mechanism_id", "in", ["exact_valid_shift", "systematic_misbinding"]),
            ],
        )
    else:
        route_round = read_frame(route_path)
        route_round = route_round[
            (route_round.route_id == "arrival_assigned")
            & (route_round.mechanism_id.isin(["exact_valid_shift", "systematic_misbinding"]))
        ].copy()
    generate_all_derived(
        output_root,
        route_seed=route_seed,
        learner_seed=learner_seed,
        delay_round=delay_round,
        route_round=route_round,
        repetitions=bootstrap_repetitions,
        ci_level=RUN.ci_level,
    )

    atomic_write_json(
        output_root / "metadata" / "run_state.json",
        {
            "run_id": run_id,
            "run_tier": run_tier,
            "status": "RAW_AND_DERIVED_COMPLETE",
            "paper_result": False,
            "completed_at": utc_now(),
            "n_path_bundles": len(path_manifest),
            "n_route_round_rows": int(len(route_round)),
            "n_learner_round_rows": int(len(seeds) * len(MECHANISM_ORDER) * 2 * structural_config.horizon),
            "config_hash": effective_hash,
            "calibration_manifest_hash": calibration_hash,
            "code_commit": code_commit,
            "code_lineage": lineage,
        },
    )
    atomic_write_json(
        STATUS_DIR / f"{run_tier}_run_status.json",
        {
            "stage": f"{run_tier}_run",
            "status": "PASS",
            "paper_result": False,
            "output": f"outputs/{run_tier}",
            "code_commit": code_commit,
            "code_lineage": lineage,
            "completed_at": utc_now(),
        },
    )
    refresh_output_manifest(output_root)
    return output_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_tier", choices=("fast", "full"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    output = execute(args.run_tier, force=args.force)
    print("PRIMARY_RUN_COMPLETE")
    print(f"run_tier={args.run_tier}")
    print("paper_result=false")
    print(f"output={output}")
    print("next=self_check.py")


if __name__ == "__main__":
    main()

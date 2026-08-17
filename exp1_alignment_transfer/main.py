from __future__ import annotations

"""Primary execution entry point for Experiment 1."""

from dataclasses import asdict
import argparse
import json
from pathlib import Path
import shutil
from typing import Any

import pandas as pd

from config import EXPERIMENT_ID, calibration_config_hash
from src.artifact_io import (
    atomic_write_csv,
    atomic_write_json,
    atomic_write_parquet,
    code_lineage,
    exp1_stage_source_hashes,
    git_commit,
    hash_payload,
    utc_now,
    ParquetStreamWriter,
    refresh_output_manifest,
)
from src.contracts import CalibrationError
from src.derived import rebuild_derived_from_scientific_artifacts
from src.run_provenance import (
    ensure_calibration_stage_provenance,
    write_fresh_exp1_provenance,
)
from src.runner import RunMetadata
from src.scientific_execution import (
    iter_primary_bundles,
    resolve_run_spec,
    run_primary_bundle,
)


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
    calibration_stage = ensure_calibration_stage_provenance(
        PROJECT_ROOT, manifest, allow_current_manifest=True
    )
    current_calibration_hash = exp1_stage_source_hashes(PROJECT_ROOT)[
        "calibration_source_hash"
    ]
    if calibration_stage.get("calibration_source_hash") != current_calibration_hash:
        raise CalibrationError(
            "Calibration was generated from different calibration-stage source. "
            "Run calibrate.py --force only after an approved change memo."
        )
    if calibration_stage.get("calibration_config_hash") != calibration_config_hash():
        raise CalibrationError(
            "Calibration was generated under a different calibration-stage config. "
            "Run calibrate.py --force only after an approved change memo."
        )
    return {
        "manifest": manifest,
        "stage_provenance": calibration_stage,
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
        current_stage_hashes = exp1_stage_source_hashes(PROJECT_ROOT)
        fast_scientific_hash = fast_payload.get("scientific_generation_source_hash")
        if fast_scientific_hash:
            if fast_scientific_hash != current_stage_hashes["scientific_generation_source_hash"]:
                raise RuntimeError(
                    "Full run is blocked because fast validation used different scientific-generation source"
                )
        elif fast_payload.get("code_lineage") != code_lineage(PROJECT_ROOT):
            raise RuntimeError(
                "Full run is blocked because fast validation used a different legacy code lineage"
            )
        if fast_payload.get("calibration_manifest_hash") != hash_payload(calibration["manifest"]):
            raise RuntimeError("Full run is blocked because fast validation used a different calibration manifest")
    spec = resolve_run_spec(run_tier, calibration)
    structural_config = spec.structural_config
    learner_config = spec.learner_config
    effective_hash = spec.effective_config_hash
    output_root = OUTPUTS_DIR / run_tier
    _prepare_output(output_root, force=force)

    code_commit = git_commit(PROJECT_ROOT)
    lineage = code_lineage(PROJECT_ROOT)
    stage_hashes = exp1_stage_source_hashes(PROJECT_ROOT)
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
            **stage_hashes,
            "effective_structural_config": asdict(structural_config),
            "effective_learner_config": asdict(learner_config),
            "seeds": list(spec.seeds),
            "mechanisms": list(spec.mechanisms),
            "bootstrap_repetitions": spec.bootstrap_repetitions,
            "config_hash": effective_hash,
            "calibration_manifest_hash": calibration_hash,
            "calibration_source_hash": stage_hashes["calibration_source_hash"],
        },
    )

    path_rows = []
    route_seed_frames = []
    learner_seed_frames = []
    route_writer = ParquetStreamWriter(output_root / "raw" / "exp1_route_diagnostic_rounds.parquet")
    learner_writer = ParquetStreamWriter(output_root / "raw" / "exp1_learner_consequence_rounds.parquet")
    delay_writer = ParquetStreamWriter(output_root / "raw" / "exp1_delay_source_rounds.parquet")

    try:
        for bundle in iter_primary_bundles(spec, calibration):
            result = run_primary_bundle(bundle, metadata, spec, calibration)
            path_rows.append(result.path_manifest_row)
            route_writer.write(result.route_round)
            learner_writer.write(result.learner_round)
            delay_writer.write(result.delay_round)
            route_seed_frames.append(result.route_seed)
            learner_seed_frames.append(result.learner_seed)
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

    aggregation_inputs = rebuild_derived_from_scientific_artifacts(
        output_root, run_tier
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
            "n_route_round_rows": aggregation_inputs["route_diagnostic_rows"],
            "n_learner_round_rows": int(
                len(spec.seeds)
                * len(spec.mechanisms)
                * 2
                * structural_config.horizon
            ),
            "config_hash": effective_hash,
            "calibration_manifest_hash": calibration_hash,
            "code_commit": code_commit,
            "code_lineage": lineage,
            **stage_hashes,
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
            **stage_hashes,
            "completed_at": utc_now(),
        },
    )
    write_fresh_exp1_provenance(output_root, PROJECT_ROOT)
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

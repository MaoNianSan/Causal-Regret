"""Pipeline stages, immutable-run rules, and resume compatibility checks."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

from code_version import code_version
from config import ExperimentConfig, ensure_output_dirs
from design_contract import EVALUATION_ARRAY_SCHEMA_VERSION, design_contract_hash
from utilities import set_run_metadata, sha256_file


STAGES = (
    "Validate input schema and freeze contracts",
    "Normalize events and freeze actions",
    "Construct source-indexed delayed targets",
    "Freeze history-only audit design",
    "Select alpha and fit observable proxy routes",
    "Build cross-fitted evaluation arrays",
    "Evaluate score, reference-pair gap, and ranking",
    "Run user-cluster resampling sensitivity",
    "Render frozen paper interfaces",
    "Finalize manifests and report",
)


def print_stage(index: int, message: str) -> None:
    print(f"[{index}/{len(STAGES)}] {message}", flush=True)


def clean_active_output(output_dir: Path) -> None:
    manifest_path = output_dir / "metadata" / "run_manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if bool(existing.get("paper_result", False)):
            raise RuntimeError("Refusing to clean a promoted paper result.")
    legacy = output_dir / "legacy"
    backup = None
    if legacy.exists() and any(legacy.iterdir()):
        backup = output_dir.parent / f".{output_dir.name}_legacy_backup"
        if backup.exists():
            shutil.rmtree(backup)
        shutil.copytree(legacy, backup)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    ensure_output_dirs(output_dir)
    if backup is not None:
        shutil.copytree(backup, output_dir / "legacy", dirs_exist_ok=True)
        shutil.rmtree(backup)


def input_manifest(paths: list[Path], input_root: Path) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "file_name": path.name,
                "relative_path": (
                    path.relative_to(input_root).as_posix()
                    if path.is_relative_to(input_root)
                    else str(path)
                ),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "sha256": sha256_file(path) if path.exists() else "",
            }
            for path in paths
        ]
    )


def config_sha256(cfg: ExperimentConfig) -> str:
    payload = json.dumps(cfg.to_dict(), sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def input_manifest_sha256(frame: pd.DataFrame) -> str:
    payload = "|".join(frame.sort_values("file_name")["sha256"].astype(str)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def set_primary_run_metadata(
    manifest: dict[str, object],
    cfg: ExperimentConfig,
    version: dict[str, str],
) -> None:
    set_run_metadata(
        {
            "run_id": manifest["run_id"],
            "run_tier": manifest["run_tier"],
            "paper_result": False,
            "analysis_tier": "primary",
            "experiment_id": cfg.experiment_id,
            "config_hash": manifest.get("config_hash", "unknown"),
            "input_manifest_hash": manifest.get("input_manifest_hash", "unknown"),
            **version,
        }
    )


def contract_hash_fields(output_dir: Path) -> dict[str, object]:
    registry = output_dir / "tables" / "exp3_metric_registry.csv"
    selection = output_dir / "metadata" / "exp3_ridge_selection_manifest.json"
    return {
        "design_contract_hash": design_contract_hash(),
        "metric_registry_hash": sha256_file(registry),
        "selected_alpha_manifest_hash": sha256_file(selection),
        "evaluation_array_schema_version": EVALUATION_ARRAY_SCHEMA_VERSION,
    }


def validate_resume_compatibility(
    project_root: Path,
    output_dir: Path,
    manifest: dict[str, object],
    run_tier: str,
    cfg: ExperimentConfig,
) -> dict[str, str]:
    version = code_version(project_root)
    if str(manifest.get("run_tier")) != run_tier:
        raise RuntimeError("Resume run tier does not match the existing manifest.")
    if any(manifest.get(key) != value for key, value in version.items()):
        raise RuntimeError("Resume source-tree hash is incompatible with the existing run.")
    required = {
        "config_hash": config_sha256(cfg),
        "design_contract_hash": design_contract_hash(),
        "evaluation_array_schema_version": EVALUATION_ARRAY_SCHEMA_VERSION,
    }
    for key, expected in required.items():
        if manifest.get(key) != expected:
            raise RuntimeError(f"Resume {key} is incompatible with the active scientific contract.")
    current_hashes = contract_hash_fields(output_dir)
    for key in ("metric_registry_hash", "selected_alpha_manifest_hash"):
        if manifest.get(key) != current_hashes[key]:
            raise RuntimeError(f"Resume {key} does not match the frozen run artifact.")
    return version


_clean_active_output = clean_active_output
_input_manifest = input_manifest

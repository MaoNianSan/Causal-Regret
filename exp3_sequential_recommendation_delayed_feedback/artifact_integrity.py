"""Frozen artifact verification and slim archival package construction."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

from code_version import code_version, source_files, source_tree_manifest
from run_reporting import write_run_report
from utilities import build_artifact_manifest, save_json, sha256_file


def _as_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"true", "1"})


def verify_artifact_manifest(output_dir: Path, *, archival: bool) -> tuple[bool, str]:
    """Verify the frozen run manifest, optionally only for archive-required rows."""
    manifest_path = output_dir / "manifest" / "artifact_manifest.csv"
    if not manifest_path.exists():
        manifest_path = output_dir / "metadata" / "artifacts_manifest.csv"
    if not manifest_path.exists():
        return False, "artifact manifest is missing"
    table = pd.read_csv(manifest_path)
    required_columns = {"relative_path", "size_bytes", "sha256", "archive_required"}
    if not required_columns.issubset(table.columns):
        return False, f"artifact manifest columns missing: {sorted(required_columns - set(table.columns))}"
    checked = table[_as_bool(table["archive_required"])] if archival else table
    for row in checked.itertuples(index=False):
        path = output_dir / str(row.relative_path)
        if not path.exists():
            return False, f"required artifact missing: {row.relative_path}"
        if path.stat().st_size != int(row.size_bytes):
            return False, f"artifact size mismatch: {row.relative_path}"
        if sha256_file(path) != str(row.sha256):
            return False, f"artifact hash mismatch: {row.relative_path}"
    role = "archive-required" if archival else "complete-run"
    return True, f"verified {len(checked)} {role} frozen artifact hashes"


def _synchronize_archival_status(output_dir: Path, status: str) -> None:
    manifest_path = output_dir / "metadata" / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["archival_integrity_check_status"] = status
    save_json(manifest, manifest_path)
    alias = output_dir / "manifest" / "run_manifest.json"
    save_json(manifest, alias)
    report = write_run_report(output_dir, manifest)
    shutil.copy2(report, output_dir / "EXP3_RUN_REPORT.md")

    check_path = output_dir / "checks" / "exp3_self_check.json"
    if check_path.exists():
        check = json.loads(check_path.read_text(encoding="utf-8"))
        check["archival_integrity_check_status"] = status
        save_json(check, check_path)
    for name in ("exp3_self_check.csv", "exp3_self_check_summary.csv"):
        summary_path = output_dir / "checks" / name
        if summary_path.exists():
            summary = pd.read_csv(summary_path)
            summary["archival_integrity_check_status"] = status
            summary.to_csv(summary_path, index=False)
    build_artifact_manifest(output_dir)


def _copy_source_and_audit(project_root: Path, package_root: Path) -> None:
    for source in source_files(project_root):
        relative = source.relative_to(project_root)
        target = package_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    audit_root = project_root / "audit"
    if audit_root.exists():
        for source in sorted(path for path in audit_root.rglob("*") if path.is_file()):
            if source.suffix.lower() not in {".md", ".json", ".txt", ".csv", ".diff"}:
                continue
            target = package_root / source.relative_to(project_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def verify_archival_package(package_root: Path, run_id: str) -> dict[str, Any]:
    """Verify a slim archive without claiming independent reconstruction."""
    package_root = package_root.resolve()
    output_dir = package_root / "outputs" / run_id
    manifest_path = output_dir / "metadata" / "run_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"ARCHIVAL_VERIFY_BLOCKED: missing run manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact_ok, detail = verify_artifact_manifest(output_dir, archival=True)
    current_version = code_version(package_root)
    version_ok = (
        manifest.get("code_version_type") == current_version["code_version_type"]
        and manifest.get("code_version") == current_version["code_version"]
        and manifest.get("code_version") != "unknown"
    )
    processed_absent = not (output_dir / "processed").exists()
    independent_frozen = manifest.get("independent_self_check_status") == "PASS"
    passed = artifact_ok and version_ok and processed_absent and independent_frozen
    result = {
        "verification_role": "archival_integrity_only_not_independent_reconstruction",
        "archival_integrity_check_status": "PASS" if passed else "FAIL",
        "independent_self_check_status": manifest.get("independent_self_check_status"),
        "independent_self_check_is_frozen": True,
        "processed_event_artifacts_present": not processed_absent,
        "artifact_hash_status": "PASS" if artifact_ok else "FAIL",
        "artifact_hash_detail": detail,
        "code_version_status": "PASS" if version_ok else "FAIL",
        **current_version,
    }
    if not passed:
        raise RuntimeError("ARCHIVAL_INTEGRITY_FAIL: " + json.dumps(result, sort_keys=True))
    return result


def create_archival_package(
    project_root: Path,
    output_dir: Path,
    *,
    package_dir: Path | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    """Create and independently verify a source-complete, data-trimmed run archive."""
    project_root = project_root.resolve()
    output_dir = output_dir.resolve()
    manifest = json.loads((output_dir / "metadata" / "run_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("independent_self_check_status") != "PASS" or manifest.get("final_engineering_status") != "PASS":
        raise RuntimeError("ARCHIVE_BLOCKED: an independent self-check PASS is required first")
    full_ok, full_detail = verify_artifact_manifest(output_dir, archival=False)
    if not full_ok:
        raise RuntimeError(f"ARCHIVE_BLOCKED: complete-run artifact verification failed: {full_detail}")

    _synchronize_archival_status(output_dir, "PASS")
    manifest = json.loads((output_dir / "metadata" / "run_manifest.json").read_text(encoding="utf-8"))
    run_id = str(manifest["run_id"])
    package_dir = (package_dir or project_root / "deliverables" / f"{run_id}-archival").resolve()
    deliverables = (project_root / "deliverables").resolve()
    if package_dir.parent != deliverables:
        raise RuntimeError("Archive staging directory must be a direct child of project deliverables/")
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)
    _copy_source_and_audit(project_root, package_dir)

    artifact_table = pd.read_csv(output_dir / "manifest" / "artifact_manifest.csv")
    for relative in artifact_table.loc[_as_bool(artifact_table["archive_required"]), "relative_path"]:
        source = output_dir / str(relative)
        target = package_dir / "outputs" / run_id / str(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for relative in ("metadata/artifacts_manifest.csv", "manifest/artifact_manifest.csv"):
        source = output_dir / relative
        target = package_dir / "outputs" / run_id / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    source_manifest = pd.DataFrame(source_tree_manifest(project_root))
    source_manifest_path = package_dir / "manifest" / "source_tree_manifest.csv"
    source_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    source_manifest.to_csv(source_manifest_path, index=False)
    result = verify_archival_package(package_dir, run_id)
    save_json(result, package_dir / "ARCHIVAL_INTEGRITY_CHECK.json")
    archive_base = package_dir.parent / package_dir.name
    zip_path = Path(shutil.make_archive(str(archive_base), "zip", root_dir=package_dir))
    return package_dir, zip_path, result

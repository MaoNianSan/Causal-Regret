"""Deterministic source-tree versioning for Exp3."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path


SOURCE_SUFFIXES = {".py", ".md", ".txt", ".ini"}
SOURCE_FILENAMES = {"requirements.txt"}
EXCLUDED_SOURCE_RELATIVE_PATHS = {"docs/EXP3_REDESIGN_IMPLEMENTATION_REPORT.md"}
EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "audit",
    "deliverables",
    "inputs",
    "outputs",
    "validation",
}


def source_files(project_root: Path) -> list[Path]:
    """Return the sorted code, configuration, test, and documentation source set."""
    project_root = project_root.resolve()
    selected: list[Path] = []
    for root, directories, filenames in os.walk(project_root):
        directories[:] = sorted(
            directory for directory in directories if directory not in EXCLUDED_PARTS
        )
        root_path = Path(root)
        for filename in sorted(filenames):
            path = root_path / filename
            relative = path.relative_to(project_root)
            if relative.as_posix() in EXCLUDED_SOURCE_RELATIVE_PATHS:
                continue
            if path.name in SOURCE_FILENAMES or path.suffix.lower() in SOURCE_SUFFIXES:
                selected.append(path)
    return sorted(selected, key=lambda path: path.relative_to(project_root).as_posix())


def source_tree_manifest(project_root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in source_files(project_root):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(
            {
                "relative_path": path.relative_to(project_root.resolve()).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": digest,
            }
        )
    return rows


def source_tree_sha256(project_root: Path) -> str:
    """Hash the sorted ``relative path + per-file hash`` source inventory."""
    rows = source_tree_manifest(project_root)
    payload = "".join(f"{row['relative_path']}\t{row['sha256']}\n" for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def code_version(project_root: Path) -> dict[str, str]:
    return {
        "code_version_type": "source_tree_sha256",
        "code_version": source_tree_sha256(project_root),
    }

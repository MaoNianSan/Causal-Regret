"""Deterministic source-tree versioning for Exp3."""
from __future__ import annotations

import hashlib
from pathlib import Path


SOURCE_SUFFIXES = {".py", ".md", ".txt", ".ini"}
SOURCE_FILENAMES = {"requirements.txt"}
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
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(project_root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
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

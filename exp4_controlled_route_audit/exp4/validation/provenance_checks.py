"""Artifact provenance and figure reconstruction checks."""

from __future__ import annotations

import json
from pathlib import Path

from exp4.outputs.writers import sha256_file


def figure_sources_reconstructable(run_dir: Path, figure_ids: tuple[str, ...]) -> tuple[bool, str]:
    failures: list[str] = []
    for figure_id in figure_ids:
        metadata_path = run_dir / "figures" / "metadata" / f"{figure_id}_metadata.json"
        if not metadata_path.exists():
            failures.append(f"missing metadata:{figure_id}")
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        for relative, expected_hash in metadata["source_file_hashes"].items():
            source = run_dir / relative
            if not source.exists() or sha256_file(source) != expected_hash:
                failures.append(f"source mismatch:{figure_id}:{relative}")
    return not failures, "; ".join(failures) if failures else "all figure sources match stored hashes"


def manifest_paths_are_relative_and_exist(run_dir: Path, manifest_paths: list[Path]) -> tuple[bool, str]:
    import pandas as pd

    failures: list[str] = []
    for manifest_path in manifest_paths:
        frame = pd.read_csv(manifest_path)
        for column in ("trajectory_file", "route_map_file"):
            if column not in frame.columns:
                continue
            for value in frame[column].dropna():
                path = Path(str(value))
                if path.is_absolute() or not (run_dir / path).exists():
                    failures.append(f"{manifest_path.name}:{column}:{value}")
    return not failures, "; ".join(failures) if failures else "all stored paths are relative and exist"

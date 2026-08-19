"""Validation for presentation previews; this module never invokes science code."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from . import SPEC_ID
from .common import LONG_FORM_COLUMNS, PreviewLayout, read_json, sha256_file, write_json
from presentation_sources import PresentationSource


def _bundle_paths(layout: PreviewLayout, figure_id: str, section: str) -> dict[str, Path]:
    base = layout.base / "figures" / section
    return {
        "pdf": base / "pdf" / f"{figure_id}.pdf",
        "svg": base / "svg" / f"{figure_id}.svg",
        "png": base / "png" / f"{figure_id}.png",
        "data": base / "data" / f"{figure_id}.csv",
        "metadata": base / "metadata" / f"{figure_id}.json",
    }


def _validate_bundle(
    layout: PreviewLayout, figure_id: str, section: str, expected_paper_result: bool = False
) -> list[dict[str, Any]]:
    paths = _bundle_paths(layout, figure_id, section)
    results: list[dict[str, Any]] = []
    for label, path in paths.items():
        results.append({"check": f"{figure_id}:{label}:nonempty", "passed": path.exists() and path.stat().st_size > 0, "details": str(path)})
    if not all(path.exists() and path.stat().st_size > 0 for path in paths.values()):
        return results
    frame = pd.read_csv(paths["data"])
    missing = [column for column in LONG_FORM_COLUMNS if column not in frame.columns]
    results.append({"check": f"{figure_id}:long_form_schema", "passed": not missing, "details": ", ".join(missing) if missing else "complete"})
    metadata = read_json(paths["metadata"])
    results.extend([
        {"check": f"{figure_id}:spec", "passed": metadata.get("spec_id") == SPEC_ID, "details": str(metadata.get("spec_id"))},
        {"check": f"{figure_id}:paper_result_contract", "passed": metadata.get("paper_result") is expected_paper_result, "details": str(metadata.get("paper_result"))},
        {"check": f"{figure_id}:source_hashes", "passed": bool(metadata.get("source_file_hashes")), "details": str(len(metadata.get("source_file_hashes", {})))},
        {"check": f"{figure_id}:three_graphic_hashes", "passed": set(metadata.get("figure_file_hashes", {})) == {paths["pdf"].name, paths["svg"].name, paths["png"].name}, "details": str(metadata.get("figure_file_hashes", {}).keys())},
    ])
    svg_text = paths["svg"].read_text(encoding="utf-8", errors="ignore")
    results.append({"check": f"{figure_id}:svg_live_text", "passed": "<text" in svg_text, "details": "SVG text elements"})
    layout_checks = metadata.get("layout_checks")
    results.append(
        {
            "check": f"{figure_id}:layout_gates_recorded",
            "passed": isinstance(layout_checks, list) and bool(layout_checks),
            "details": (
                "no layout gates recorded"
                if not isinstance(layout_checks, list) or not layout_checks
                else metadata.get("layout_profile")
            ),
        }
    )
    if isinstance(layout_checks, list):
        for row in layout_checks:
            results.append(
                {
                    "check": f"{figure_id}:{row['check']}",
                    "passed": bool(row["passed"]),
                    "details": str(row.get("details", "")),
                }
            )
    for filename, digest in metadata.get("figure_file_hashes", {}).items():
        file_path = paths["pdf"].parent / filename if filename.endswith(".pdf") else paths["svg"].parent / filename if filename.endswith(".svg") else paths["png"].parent / filename
        results.append({"check": f"{figure_id}:hash:{filename}", "passed": file_path.exists() and sha256_file(file_path) == digest, "details": str(file_path)})
    return results


def _source_contract(source: PresentationSource) -> list[dict[str, Any]]:
    results = [{"check": "source_files_present", "passed": not source.missing_files(), "details": ", ".join(map(str, source.missing_files()))}]
    if source.experiment == "Exp1":
        payload = json.loads((source.source_run / "metadata/exp1_run_lineage.json").read_text(encoding="utf-8"))
        observed = payload.get("scientific_generation_config_hash")
        results.append({"check": "exp1_scientific_generation_config_hash", "passed": observed == source.config_hash, "details": str(observed)})
    elif source.experiment == "Exp4":
        payload = json.loads((source.source_run / "logs/exp4_stage_config_migration.json").read_text(encoding="utf-8"))
        observed = payload.get("scientific_config_hash")
        results.append({"check": "exp4_scientific_config_hash", "passed": observed == source.config_hash, "details": str(observed)})
        run = json.loads((source.source_run / "logs/run_config.json").read_text(encoding="utf-8"))
        results.extend([
            {"check": "exp4_v3_schema", "passed": run.get("result_schema") == "exp4_controlled_route_audit_v3", "details": str(run.get("result_schema"))},
            {"check": "exp4_source_paper_result_matches", "passed": run.get("paper_result") == source.scientific_source_paper_result, "details": str(run.get("paper_result"))},
        ])
    elif source.experiment == "Exp3":
        frame = pd.read_csv(source.source_run / "tables/exp3_primary_route_results.csv")
        row = frame.loc[frame.route_id.eq("arrival_carrier"), "maximum_heldout_reference_pair_gap_error"]
        actual = float(row.iloc[0]) if len(row) == 1 else float("nan")
        results.append({"check": "exp3_current_arrival_max_gap_source", "passed": abs(actual - 0.6417907611) < 1e-9, "details": repr(actual)})
    return results


def _manifest_artifact_checks(
    layout: PreviewLayout, manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for relative, digest in manifest.get("artifact_hashes", {}).items():
        path = layout.base / relative
        results.append(
            {
                "check": f"artifact_hash:{relative}",
                "passed": path.exists() and sha256_file(path) == digest,
                "details": str(path),
            }
        )
    return results


def validate_preview(
    source: PresentationSource, preview_root: Path, mode: str = "preview"
) -> dict[str, Any]:
    layout = PreviewLayout(preview_root, source.experiment_id, source.run_id, mode=mode)
    manifest_path = layout.base / "manifests/presentation_manifest.json"
    figure_ids: list[str] = []
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        figure_ids = manifest.get("figure_ids", [])
        results = _source_contract(source) + _manifest_artifact_checks(layout, manifest)
    else:
        results = _source_contract(source)
    for figure_id in figure_ids:
        results.extend(
            _validate_bundle(layout, figure_id, "main", expected_paper_result=source.paper_result)
        )
    appendix_path = layout.base / "manifests/appendix_manifest.json"
    if appendix_path.exists():
        appendix = read_json(appendix_path)
        results.extend(_manifest_artifact_checks(layout, appendix))
        for figure_id in appendix.get("figure_ids", []):
            results.extend(
                _validate_bundle(
                    layout, figure_id, "appendix", expected_paper_result=source.paper_result
                )
            )
    results.append({"check": "presentation_manifest_exists", "passed": manifest_path.exists(), "details": str(manifest_path)})
    passed = all(row["passed"] for row in results)
    payload = {"spec_id": SPEC_ID, "experiment_id": source.experiment_id, "run_id": source.run_id, "paper_result": source.paper_result, "passed": passed, "checks": results}
    layout.ensure()
    write_json(layout.base / "validation/presentation_validation.json", payload)
    return payload

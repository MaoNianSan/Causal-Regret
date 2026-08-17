from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from . import SPEC_ID
from .common import (
    PreviewLayout,
    copy_table_bundle,
    hash_payload,
    read_json,
    sha256_file,
    utc_now,
    write_json,
)
from presentation_sources import PresentationSource, load_run_manifest


ROOT = Path(__file__).resolve().parents[1]
RENDERER_PATHS = {
    "Exp1": ROOT / "exp1_alignment_transfer" / "presentation.py",
    "Exp2": ROOT / "exp2_real_delayed_conversion_logs" / "exp2_core" / "reporting" / "presentation.py",
    "Exp3": ROOT / "exp3_sequential_recommendation_delayed_feedback" / "presentation.py",
    "Exp4": ROOT / "exp4_controlled_route_audit" / "exp4" / "reporting" / "presentation.py",
}


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _scientific_lineage(source: PresentationSource) -> str:
    manifest = load_run_manifest(source)
    if source.experiment == "Exp1":
        lineage = read_json(source.source_run / "metadata/exp1_run_lineage.json")
        return str(lineage["scientific_generation_source_hash"])
    if source.experiment == "Exp4":
        lineage = read_json(source.source_run / "logs/exp4_stage_hash_migration.json")
        return str(lineage["current_new_simulation_hash"])
    return str(
        manifest.get(
            "code_identity",
            manifest.get("code_version", manifest.get("source_code_hash", "unknown")),
        )
    )


def _presentation_code_hash(code_paths: Iterable[Path]) -> str:
    paths = {Path(__file__).resolve(), (Path(__file__).parent / "common.py").resolve()}
    paths.update(Path(path).resolve() for path in code_paths)
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.as_posix()):
        try:
            relative = path.relative_to(ROOT).as_posix()
        except ValueError:
            relative = path.as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def figure_metadata(
    source: PresentationSource,
    *,
    claim: str,
    panels: dict[str, str],
    metrics: dict[str, str],
    boundary: str,
    code_paths: Iterable[Path],
    contract: dict[str, Any],
    sample_count: Any = "NA",
    uncertainty: str = "",
    marker_semantics: dict[str, str] | None = None,
) -> dict[str, Any]:
    manifest = load_run_manifest(source)
    code_hash = _presentation_code_hash(code_paths)
    presentation_lineage = "presentation:" + hash_payload(
        {"spec_id": SPEC_ID, "code_hash": code_hash, "figure_contract": contract}
    )
    return {
        "experiment_id": source.experiment_id,
        "run_id": source.run_id,
        "run_tier": source.run_tier,
        "scientific_source_paper_result": source.scientific_source_paper_result,
        "result_schema": source.result_schema,
        "config_hash": source.config_hash,
        "input_manifest_hash": manifest.get("input_manifest_hash", "NA"),
        "narrative_claim": claim,
        "question_or_claim": claim,
        "panel_definitions": panels,
        "metric_definitions": metrics,
        "interpretation_boundary": boundary,
        "sample_or_seed_count": sample_count,
        "uncertainty_semantics": uncertainty,
        "uncertainty_definition": uncertainty,
        "marker_semantics": marker_semantics or {},
        "scientific_source_lineage": _scientific_lineage(source),
        "presentation_source_lineage": presentation_lineage,
        "presentation_build_commit": _git_head(),
        "presentation_code_hash": code_hash,
        "source_run_path": str(source.source_run),
        "presentation_contract": contract,
    }


def write_standard_table(
    layout: PreviewLayout, source: Path, stem: str, *, semantics: str
) -> None:
    copy_table_bundle(
        source,
        layout,
        stem=stem,
        metadata={"semantics": semantics, "paper_result": False},
    )


def write_table_frame(
    layout: PreviewLayout,
    frame: pd.DataFrame,
    stem: str,
    *,
    semantics: str,
    source_files: Iterable[Path],
) -> None:
    layout.ensure()
    csv_path = layout.base / "tables" / "csv" / f"{stem}.csv"
    tex_path = layout.base / "tables" / "tex" / f"{stem}.tex"
    metadata_path = layout.base / "tables" / "metadata" / f"{stem}.json"
    frame.to_csv(csv_path, index=False, float_format="%.17g")
    tex_path.write_text(frame.to_latex(index=False, escape=True), encoding="utf-8")
    write_json(
        metadata_path,
        {
            "spec_id": SPEC_ID,
            "table_id": stem,
            "paper_result": False,
            "semantics": semantics,
            "source_file_hashes": {
                str(path): sha256_file(path) for path in source_files if path.exists()
            },
            "csv_sha256": sha256_file(csv_path),
            "tex_sha256": sha256_file(tex_path),
        },
    )


def _artifact_hashes(layout: PreviewLayout) -> dict[str, str]:
    excluded = {"manifests", "validation"}
    paths = [
        path
        for path in layout.base.rglob("*")
        if path.is_file() and not excluded.intersection(path.relative_to(layout.base).parts)
    ]
    return {
        path.relative_to(layout.base).as_posix(): sha256_file(path)
        for path in sorted(paths)
    }


def write_manifest(
    layout: PreviewLayout,
    source: PresentationSource,
    *,
    appendix: bool = False,
    figure_ids: list[str] | None = None,
) -> None:
    layout.ensure()
    payload = {
        "spec_id": SPEC_ID,
        "experiment_id": source.experiment_id,
        "run_id": source.run_id,
        "run_tier": source.run_tier,
        "paper_result": False,
        "scientific_source_paper_result": source.scientific_source_paper_result,
        "promotion_status": "NOT_PROMOTED_PRESENTATION_PREVIEW",
        "figure_ids": figure_ids or [],
        "artifact_hashes": _artifact_hashes(layout),
        "generated_at": utc_now(),
    }
    name = "appendix_manifest.json" if appendix else "presentation_manifest.json"
    write_json(layout.base / "manifests" / name, payload)


def load_renderer_module(experiment: str) -> Any:
    path = RENDERER_PATHS.get(experiment)
    if path is None:
        raise KeyError(experiment)
    module_name = f"_cr_exp_output_{experiment.lower()}"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load presentation renderer: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def render_source(source: PresentationSource, preview_root: Path) -> dict[str, Any]:
    module = load_renderer_module(source.experiment)
    return module.render_presentation(source, preview_root)


def write_overview_table(layout: PreviewLayout) -> None:
    rows = [
        ["Exp1", "Controlled simulator plus scalar-feedback learner", "exact-valid, matched-mean misaligned, systematic misbinding", "alignment budget, structural regret, binding contrast", "Action-gap alignment controls transfer; learner allocation is a separate consequence."],
        ["Exp2", "Criteo delayed-conversion log", "arrival accounting vs four source-time attribution rules", "allocation TV and Kendall tau-b", "Attribution sensitivity on a fixed cohort; not causal attribution or policy value."],
        ["Exp3", "KuaiRand-1K held-out logged support", "Arrival carrier, Historical mean, Ridge", "score, pairwise gap, ranking recovery", "Score recovery need not transfer to decision recovery; not OPE or causal regret."],
        ["Exp4", "Controlled route/audit/calibration simulator", "label retention, audit selection/IPW, calibration controls", "D_pair, audit bias/RMSE, OOF recoverability", "Population alignment, audit reliability, and calibratability are distinct."],
    ]
    frame = pd.DataFrame(
        rows,
        columns=[
            "Exp.",
            "Data/design",
            "Route contrast",
            "Primary readout",
            "Supported inference and boundary",
        ],
    )
    layout.ensure()
    csv_path = layout.base / "tables/csv/tab_experimental_evidence_map.csv"
    tex_path = layout.base / "tables/tex/tab_experimental_evidence_map.tex"
    frame.to_csv(csv_path, index=False, float_format="%.17g")
    tex_path.write_text(frame.to_latex(index=False, escape=True), encoding="utf-8")
    write_json(
        layout.base / "tables/metadata/tab_experimental_evidence_map.json",
        {
            "spec_id": SPEC_ID,
            "table_id": "tab_experimental_evidence_map",
            "paper_result": False,
            "editorial_only": True,
            "csv_sha256": sha256_file(csv_path),
            "tex_sha256": sha256_file(tex_path),
        },
    )


def write_appendix_order(layout: PreviewLayout) -> None:
    path = layout.base / "manifests/appendix_manifest.json"
    existing = read_json(path) if path.exists() else {}
    existing.update(
        {
            "spec_id": SPEC_ID,
            "paper_result": False,
            "experiment_id": existing.get("experiment_id", layout.experiment_id),
            "run_id": existing.get("run_id", layout.run_id),
            "figure_ids": existing.get("figure_ids", []),
            "artifact_hashes": _artifact_hashes(layout),
            "appendix_order": [
                {"id": "C.1", "items": ["reporting", "uncertainty", "provenance"]},
                {"id": "C.2", "items": ["Exp1 protocol", "complete table", "diagnostics", "targeted validation"]},
                {"id": "C.3", "items": ["Exp2 cohort", "route definitions", "complete pairwise", "diagnostics", "robustness"]},
                {"id": "C.4", "items": ["Exp3 support", "primary tables", "three composites", "CV/coefficient", "resampling diagnostics"]},
                {"id": "C.5", "items": ["Exp4 v3 parameters", "Module A", "audit", "calibration", "three composites"]},
                {"id": "C.6", "items": ["artifact lineage"]},
            ],
            "generated_at": utc_now(),
        }
    )
    write_json(path, existing)

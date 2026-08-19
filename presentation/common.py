from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd

from . import SPEC_ID

LONG_FORM_COLUMNS = [
    "figure_id",
    "panel_id",
    "experiment_id",
    "run_id",
    "run_tier",
    "paper_result",
    "analysis_tier",
    "metric_id",
    "estimand_id",
    "condition_id",
    "series_id",
    "point_estimate",
    "resampling_median",
    "interval_lower",
    "interval_upper",
    "uncertainty_role",
    "uncertainty_method",
    "repetition_count",
    "sample_count",
    "unit",
    "better_direction",
    "source_table",
    "source_row_key",
]

INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True)
class PreviewLayout:
    root: Path
    experiment_id: str
    run_id: str
    mode: str = "preview"

    @property
    def safe_run_id(self) -> str:
        return sanitize_run_id(self.run_id)

    @property
    def base(self) -> Path:
        if self.mode == "publication":
            # Canonical publication layout: one frozen promoted run per
            # experiment, so the run-id/spec nesting is collapsed.
            return self.root / self.experiment_id
        return self.root / self.experiment_id / self.safe_run_id / SPEC_ID

    def ensure(self) -> None:
        for section in ("main", "appendix"):
            for ext in ("pdf", "svg", "png", "data", "metadata"):
                (self.base / "figures" / section / ext).mkdir(
                    parents=True, exist_ok=True
                )
        for path in (
            self.base / "tables" / "csv",
            self.base / "tables" / "tex",
            self.base / "tables" / "metadata",
            self.base / "manifests",
            self.base / "validation",
        ):
            path.mkdir(parents=True, exist_ok=True)


def sanitize_run_id(value: str) -> str:
    value = INVALID_PATH_CHARS.sub("_", str(value)).strip(" .")
    value = re.sub(r"_+", "_", value)
    return value or "run"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_payload(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def configure_matplotlib() -> None:
    mpl.use("Agg", force=True)
    mpl.rcParams.update(
        {
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "font.size": 8.0,
            "axes.titlesize": 9.0,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "lines.linewidth": 0.9,
            "patch.linewidth": 0.8,
        }
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def standardize_long_form(
    frame: pd.DataFrame,
    *,
    figure_id: str,
    experiment_id: str,
    run_id: str,
    run_tier: str,
    paper_result: bool,
    analysis_tier: str = "primary",
) -> pd.DataFrame:
    result = frame.copy()
    for column in LONG_FORM_COLUMNS:
        if column not in result.columns:
            result[column] = pd.NA
    result["figure_id"] = figure_id
    result["experiment_id"] = experiment_id
    result["run_id"] = run_id
    result["run_tier"] = run_tier
    result["paper_result"] = bool(paper_result)
    result["analysis_tier"] = analysis_tier
    return result[LONG_FORM_COLUMNS]


def write_figure_bundle(
    figure: plt.Figure,
    source_data: pd.DataFrame,
    layout: PreviewLayout,
    *,
    figure_id: str,
    section: str,
    metadata: dict[str, Any],
    source_files: Iterable[Path],
    layout_profile: str | None = None,
) -> dict[str, Path]:
    if section not in {"main", "appendix"}:
        raise ValueError(section)
    layout.ensure()
    configure_matplotlib()
    # Layout regression gates: measure real rendered bounding boxes on a
    # canvas draw and fail hard before any file is written.  No gate is run
    # for callers that do not opt in via ``layout_profile``.
    layout_checks: list[dict[str, Any]] = []
    if layout_profile is not None:
        from .layout import run_layout_gates

        # Fixed-canvas normalization, applied before measurement:
        # 1. matplotlib 3.11's AutoLocator can emit the next 'nice' tick
        #    beyond vmax on narrow axes, whose label then pokes past the
        #    canvas edge.  Re-declaring MaxNLocator with prune='both' clips
        #    such ticks at draw time (explicit FixedLocator choices, e.g.
        #    colorbars, are left untouched).
        # 2. Constrained figures get a minimum outer pad: the default pad is
        #    1/24 in and dense panels can push titles/annotations up to the
        #    canvas edge.
        from matplotlib.ticker import MaxNLocator

        for axis in figure.axes:
            for ticker in (axis.xaxis, axis.yaxis):
                if isinstance(ticker.get_major_locator(), MaxNLocator):
                    ticker.set_major_locator(MaxNLocator(nbins="auto", prune="both"))
        if figure.get_constrained_layout():
            engine = figure.get_layout_engine()
            if engine is not None and hasattr(engine, "set"):
                engine.set(w_pad=0.08, h_pad=0.08)
            else:  # matplotlib < 3.6 fallback
                figure.set_constrained_layout_pads(w_pad=0.08, h_pad=0.08)

        layout_checks = run_layout_gates(figure, layout_profile)
        failures = [check for check in layout_checks if not check["passed"]]
        if failures:
            raise AssertionError(
                f"layout gates failed for {figure_id} "
                f"(profile={layout_profile}): "
                + "; ".join(f"{item['check']}: {item['details']}" for item in failures)
            )
    prefix = layout.base / "figures" / section
    pdf = prefix / "pdf" / f"{figure_id}.pdf"
    svg = prefix / "svg" / f"{figure_id}.svg"
    png = prefix / "png" / f"{figure_id}.png"
    data_path = prefix / "data" / f"{figure_id}.csv"
    meta_path = prefix / "metadata" / f"{figure_id}.json"
    # Fixed canvas dimensions are part of the contract; avoid bbox_inches=tight.
    figure.savefig(pdf)
    figure.savefig(svg)
    figure.savefig(png, dpi=300)
    # LF line endings keep the data CSV byte-stable across platforms.
    source_data.to_csv(
        data_path, index=False, float_format="%.17g", lineterminator="\n"
    )
    source_hashes = {
        str(path): sha256_file(path) for path in source_files if path.exists()
    }
    file_hashes = {path.name: sha256_file(path) for path in (pdf, svg, png)}
    source_data_hash = sha256_file(data_path)
    canvas_size = [float(value) for value in figure.get_size_inches()]
    payload = {
        "spec_id": SPEC_ID,
        "figure_id": figure_id,
        "figure_version": "v1",
        "experiment_id": metadata.get("experiment_id"),
        "narrative_claim": metadata.get("narrative_claim", ""),
        "panel_definitions": metadata.get("panel_definitions", {}),
        "metric_definitions": metadata.get("metric_definitions", {}),
        "interpretation_boundary": metadata.get("interpretation_boundary", ""),
        "question_or_claim": metadata.get(
            "question_or_claim", metadata.get("narrative_claim", "")
        ),
        "marker_semantics": metadata.get("marker_semantics", {}),
        "uncertainty_semantics": metadata.get("uncertainty_semantics", ""),
        "sample_or_seed_count": metadata.get("sample_or_seed_count", "NA"),
        "run_id": metadata.get("run_id"),
        "run_tier": metadata.get("run_tier"),
        "paper_result": bool(metadata.get("paper_result", False)),
        "scientific_source_paper_result": bool(
            metadata.get("scientific_source_paper_result", False)
        ),
        "promotion_status": metadata.get(
            "promotion_status", "NOT_PROMOTED_PRESENTATION_PREVIEW"
        ),
        "result_schema": metadata.get("result_schema", "NA"),
        "config_hash": metadata.get("config_hash", "NA"),
        "input_manifest_hash": metadata.get("input_manifest_hash", "NA"),
        "scientific_source_lineage": metadata.get("scientific_source_lineage", ""),
        "presentation_source_lineage": metadata.get("presentation_source_lineage", ""),
        "source_file_hashes": source_hashes,
        "figure_file_hashes": file_hashes,
        "source_data_file_hash": source_data_hash,
        "uncertainty_definition": metadata.get(
            "uncertainty_definition", metadata.get("uncertainty_semantics", "")
        ),
        "generated_at": utc_now(),
        "source_run_path": metadata.get("source_run_path", ""),
        "presentation_build_commit": metadata.get(
            "presentation_build_commit", "unknown"
        ),
        "presentation_code_hash": metadata.get("presentation_code_hash", ""),
        "preview_root_relative_path": str(layout.base.relative_to(layout.root)).replace(
            os.sep, "/"
        ),
        "canvas_size_inches": canvas_size,
        "png_dpi": 300,
        "source_data": str(data_path.relative_to(layout.base)).replace(os.sep, "/"),
        "layout_profile": layout_profile,
        "layout_checks": layout_checks,
        **{
            k: v
            for k, v in metadata.items()
            if k not in {"figure_file_hashes", "source_file_hashes"}
        },
    }
    write_json(meta_path, payload)
    plt.close(figure)
    return {
        "pdf": pdf,
        "svg": svg,
        "png": png,
        "data": data_path,
        "metadata": meta_path,
    }


def copy_table_bundle(
    source: Path, layout: PreviewLayout, *, stem: str, metadata: dict[str, Any]
) -> tuple[Path, Path, Path]:
    layout.ensure()
    frame = pd.read_csv(source)
    csv_path = layout.base / "tables" / "csv" / f"{stem}.csv"
    tex_path = layout.base / "tables" / "tex" / f"{stem}.tex"
    meta_path = layout.base / "tables" / "metadata" / f"{stem}.json"
    frame.to_csv(csv_path, index=False, float_format="%.17g", lineterminator="\n")
    tex_path.write_text(frame.to_latex(index=False, escape=True), encoding="utf-8")
    write_json(
        meta_path,
        {
            "spec_id": SPEC_ID,
            "table_id": stem,
            "source_file": str(source),
            "source_file_sha256": sha256_file(source),
            "csv_sha256": sha256_file(csv_path),
            "tex_sha256": sha256_file(tex_path),
            "paper_result": False,
            **metadata,
        },
    )
    return csv_path, tex_path, meta_path


def assert_no_suptitle(figure: plt.Figure) -> None:
    if figure._suptitle is not None:
        raise AssertionError("main figures must not use a figure-level suptitle")

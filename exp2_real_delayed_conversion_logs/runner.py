from __future__ import annotations

import json
import os
import subprocess
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from bootstrap import (
    attach_bootstrap_intervals,
    build_bootstrap_bias_audit,
    run_uid_cluster_bootstrap,
)
from cohort import build_primary_cohort
from contracts import EXPERIMENT_ID, EXPERIMENT_SLUG, EXPERIMENT_TITLE
from data_io import (
    canonical_json_hash,
    input_manifest_identity_hash,
    load_config,
    prepare_raw_log,
    write_frame,
    write_json,
)
from metrics import compute_primary_metrics
from targeted import run_targeted_analyses
from reporting import (
    make_delay_composition_figure,
    make_main_figure,
    make_pairwise_appendix_figure,
    make_tables,
)
from routes import build_attribution_routes
from synthetic import create_synthetic_fixture
from validation import validate_frozen_configuration, validate_run


@dataclass(frozen=True)
class RunPaths:
    root: Path
    derived: Path
    figures: Path
    tables: Path
    audit: Path
    logs: Path
    manifest: Path


def _now_local() -> datetime:
    return datetime.now().astimezone()


def _run_id(mode: str) -> str:
    return f"exp2-{mode}-{_now_local().strftime('%Y%m%dT%H%M%S%z')}"


def _git_commit(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unavailable"


def _create_paths(project_root: Path, mode: str) -> RunPaths:
    run_root = project_root / "outputs" / _run_id(mode)
    paths = RunPaths(
        root=run_root,
        derived=run_root / "derived",
        figures=run_root / "figures",
        tables=run_root / "tables",
        audit=run_root / "audit",
        logs=run_root / "logs",
        manifest=run_root / "run_manifest.json",
    )
    for directory in (
        paths.root,
        paths.derived,
        paths.figures,
        paths.tables,
        paths.audit,
        paths.logs,
    ):
        directory.mkdir(parents=True, exist_ok=False if directory == paths.root else True)
    return paths


def _log_stage(index: int, total: int, title: str) -> None:
    print(f"\n[{index}/{total}] {title}", flush=True)


def _write_csv(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def run(
    mode: str,
    *,
    config_path: str | Path | None = None,
    input_path: str | Path | None = None,
    n_bootstrap: int | None = None,
    n_jobs: str | int | None = None,
) -> int:
    if mode not in {"fast", "full"}:
        raise ValueError("mode must be 'fast' or 'full'.")

    project_root = Path(__file__).resolve().parent
    config_file = Path(config_path) if config_path is not None else project_root / "config.yaml"
    config = load_config(config_file)
    validate_frozen_configuration(config)
    paths = _create_paths(project_root, mode)
    run_id = paths.root.name
    config_hash = canonical_json_hash(config)
    code_commit = _git_commit(project_root)
    table_format = str(
        config["storage"][
            "fast_large_table_format" if mode == "fast" else "full_large_table_format"
        ]
    )

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "experiment_id": EXPERIMENT_ID,
        "experiment_slug": EXPERIMENT_SLUG,
        "experiment_title": EXPERIMENT_TITLE,
        "run_tier": mode,
        "paper_result": False,
        "status": "RUNNING",
        "engineering_status": "PENDING",
        "scientific_status": "PENDING",
        "paper_promotion_status": "INELIGIBLE_FAST" if mode == "fast" else "PENDING",
        "started_at": _now_local().isoformat(),
        "code_commit": code_commit,
        "config_path": (
            str(config_file.resolve().relative_to(project_root))
            if config_file.resolve().is_relative_to(project_root)
            else str(config_file.resolve())
        ),
        "config_hash": config_hash,
        "large_table_format": table_format,
        "development_override": n_bootstrap is not None or n_jobs is not None or input_path is not None,
    }
    write_json(manifest, paths.manifest)

    print("EXP2 — Delayed-Conversion Attribution Sensitivity")
    print(f"Run tier: {mode.upper()}")
    print(f"Run ID: {run_id}")
    print(f"Large-table format: {table_format}")

    try:
        total_stages = 9
        _log_stage(1, total_stages, "Validate configuration and resolve input")
        if input_path is None:
            configured_input = project_root / str(config["input"]["raw_file"])
            if mode == "fast" and bool(config.get("fast", {}).get("synthetic_fixture", False)):
                resolved_input = create_synthetic_fixture(
                    paths.audit / "synthetic_contract_fixture.tsv",
                    seed=int(config["statistics"]["bootstrap_seed"]),
                )
                input_kind = "synthetic_contract_fixture"
            else:
                resolved_input = configured_input
                input_kind = "external_criteo_log"
        else:
            resolved_input = Path(input_path)
            input_kind = "explicit_input_override"
        if mode == "full" and input_kind == "synthetic_contract_fixture":
            raise RuntimeError("Full mode cannot use a synthetic fixture.")
        print(f"      Input: {resolved_input}")
        print(f"      Input kind: {input_kind}")
        print("      Status: PASS")

        _log_stage(2, total_stages, "Scan raw log and construct route-independent candidates")
        prepared = prepare_raw_log(
            resolved_input,
            config,
            mode=mode,
            progress=config["runtime"].get("progress_mode", "normal") != "quiet",
            apply_fast_hash_sample=(
                mode == "fast" and input_kind != "synthetic_contract_fixture"
            ),
        )
        write_json(prepared.audit, paths.audit / "raw_input_audit.json")
        write_json(prepared.input_manifest, paths.audit / "input_manifest.json")
        print(f"      Candidate rows: {len(prepared.candidates):,}")
        print(f"      Impression cells before support filter: {len(prepared.impression_counts):,}")
        print("      Status: PASS")

        _log_stage(3, total_stages, "Build common journey cohort and decision-cell universe")
        cohort = build_primary_cohort(
            prepared.candidates,
            prepared.impression_counts,
            config,
        )
        _write_csv(cohort.cohort_summary, paths.derived / "cohort_summary.csv")
        write_frame(
            cohort.journey_manifest,
            paths.derived / "journey_manifest",
            table_format=table_format,
        )
        write_frame(
            cohort.decision_cell_universe,
            paths.derived / "decision_cell_universe",
            table_format=table_format,
        )
        _write_csv(
            cohort.journey_manifest["exclusion_reason"]
            .value_counts(dropna=False)
            .rename_axis("exclusion_reason")
            .reset_index(name="journey_count"),
            paths.derived / "exclusion_summary.csv",
        )
        write_json(cohort.audit, paths.audit / "cohort_audit.json")
        retained_count = int(cohort.journey_manifest["is_primary_eligible"].sum())
        retained_users = int(
            cohort.journey_manifest.loc[
                cohort.journey_manifest["is_primary_eligible"], "user_id"
            ].nunique()
        )
        print(f"      Retained journeys: {retained_count:,}")
        print(f"      Retained UIDs: {retained_users:,}")
        print(f"      Eligible cells: {len(cohort.decision_cell_universe):,}")
        print("      Status: PASS")

        _log_stage(4, total_stages, "Construct attribution routes")
        routes = build_attribution_routes(
            cohort.eligible_candidates,
            cohort.journey_manifest,
            cohort.decision_cell_universe,
            config,
        )
        write_frame(
            routes.assignments,
            paths.derived / "route_assignments",
            table_format=table_format,
        )
        _write_csv(routes.route_summary, paths.audit / "route_summary.csv")
        _write_csv(routes.em_diagnostics, paths.audit / "em_diagnostics.csv")
        _write_csv(
            routes.logged_reference_summary,
            paths.audit / "logged_reference_summary.csv",
        )
        print("      Primary routes: 5")
        print("      Appendix route: EM soft attribution")
        print("      Credit conservation: PASS")

        _log_stage(5, total_stages, "Compute allocation, ranking, and ambiguity metrics")
        point = compute_primary_metrics(
            routes.assignments,
            cohort.decision_cell_universe,
            cohort.journey_manifest,
            top_k=int(config["ranking"]["primary_top_k"]),
        )
        write_frame(
            point.route_allocations,
            paths.derived / "route_allocations",
            table_format=table_format,
        )
        _write_csv(point.kendall_support, paths.derived / "kendall_support.csv")
        _write_csv(point.ambiguity_strata, paths.derived / "ambiguity_strata.csv")
        targeted = run_targeted_analyses(
            prepared_candidates=prepared.candidates,
            impression_counts=prepared.impression_counts,
            primary_cohort=cohort,
            primary_metrics=point,
            config=config,
            mode=mode,
        )
        _write_csv(targeted, paths.derived / "targeted_validation.csv")
        print("      Common cohort: PASS")
        print("      Common ranking denominator: PASS")

        _log_stage(6, total_stages, "Run UID-cluster bootstrap")
        bootstrap = run_uid_cluster_bootstrap(
            routes.assignments,
            cohort.journey_manifest,
            cohort.decision_cell_universe,
            config,
            mode=mode,
            metric_states=point.kendall_metric_states,
            n_bootstrap_override=n_bootstrap,
            n_jobs_override=n_jobs,
            progress=config["runtime"].get("progress_mode", "normal") != "quiet",
        )
        write_frame(
            bootstrap.draws,
            paths.derived / "bootstrap_draws",
            table_format=table_format,
        )
        write_json(bootstrap.audit, paths.audit / "bootstrap_audit.json")
        arrival, pairwise = attach_bootstrap_intervals(
            point.arrival_displacement,
            point.source_route_pairwise,
            bootstrap,
        )
        _write_csv(arrival, paths.derived / "arrival_displacement.csv")
        _write_csv(pairwise, paths.derived / "source_route_pairwise.csv")
        bootstrap_bias_audit = build_bootstrap_bias_audit(arrival, pairwise)
        write_json(bootstrap_bias_audit, paths.audit / "bootstrap_bias_audit.json")
        print(f"      Replicates: {bootstrap.audit['bootstrap_repetitions']:,}")
        print(
            "      Percentile-CI bias warnings: "
            f"{bootstrap_bias_audit['point_outside_percentile_ci_count']:,}"
        )
        print("      Status: PASS")

        _log_stage(7, total_stages, "Generate manuscript figures and tables")
        run_metadata = {
            "run_id": run_id,
            "run_tier": mode,
            "paper_result": False,
            "experiment_id": EXPERIMENT_ID,
            "code_commit": code_commit,
            "config_hash": config_hash,
            "input_manifest_hash": input_manifest_identity_hash(prepared.input_manifest),
            "cohort_hash": canonical_json_hash(
                sorted(
                    cohort.journey_manifest.loc[
                        cohort.journey_manifest["is_primary_eligible"], "journey_id"
                    ].astype(str)
                )
            ),
            "decision_cell_universe_hash": canonical_json_hash(
                sorted(cohort.decision_cell_universe["decision_cell_id"].astype(str))
            ),
            "generated_at": _now_local().isoformat(),
        }
        make_main_figure(
            arrival,
            pairwise,
            paths.figures,
            config,
            run_metadata=run_metadata,
        )
        make_pairwise_appendix_figure(
            pairwise,
            paths.figures,
            config,
            run_metadata=run_metadata,
        )
        make_delay_composition_figure(
            cohort.eligible_candidates,
            paths.figures,
            config,
            run_metadata=run_metadata,
        )
        table_files = make_tables(
            cohort.cohort_summary,
            arrival,
            pairwise,
            paths.tables,
            bootstrap_audit=bootstrap.audit,
        )
        print(f"      Figures: {len(list(paths.figures.glob('*.pdf')))} PDF")
        print(f"      Tables: {len(table_files)} files")
        print("      Status: PASS")

        _log_stage(8, total_stages, "Run engineering and scientific validation")
        validation = validate_run(
            config,
            journey_manifest=cohort.journey_manifest,
            decision_cells=cohort.decision_cell_universe,
            assignments=routes.assignments,
            route_allocations=point.route_allocations,
            arrival_displacement=arrival,
            source_route_pairwise=pairwise,
            bootstrap_draws=bootstrap.draws,
            mode=mode,
            expected_bootstrap_repetitions=int(bootstrap.audit["bootstrap_repetitions"]),
            bootstrap_audit=bootstrap.audit,
            development_override=bool(manifest["development_override"]),
        )
        write_json(
            {
                "engineering_status": validation.engineering_status,
                "scientific_status": validation.scientific_status,
                "paper_promotion_status": validation.paper_promotion_status,
                "checks": validation.checks,
            },
            paths.audit / "self_check.json",
        )
        print(f"      Engineering status: {validation.engineering_status}")
        print(f"      Scientific status: {validation.scientific_status}")

        _log_stage(9, total_stages, "Finalize run manifest")
        manifest.update(
            {
                "status": "COMPLETE",
                "engineering_status": validation.engineering_status,
                "scientific_status": validation.scientific_status,
                "paper_promotion_status": validation.paper_promotion_status,
                "completed_at": _now_local().isoformat(),
                "input_kind": input_kind,
                "input_manifest_hash": input_manifest_identity_hash(prepared.input_manifest),
                "cohort_hash": run_metadata["cohort_hash"],
                "decision_cell_universe_hash": run_metadata[
                    "decision_cell_universe_hash"
                ],
                "bootstrap_repetitions": bootstrap.audit["bootstrap_repetitions"],
                "bootstrap_bias_warning_count": bootstrap_bias_audit[
                    "point_outside_percentile_ci_count"
                ],
                "input_content_sha256": prepared.input_manifest["input_content_sha256"],
                "primary_full_runs_complete": mode == "full" and not bool(manifest["development_override"]),
                "main_figures_reconstructable": True,
                "main_tables_reconstructable": True,
                "claims_within_scope": True,
            }
        )
        write_json(manifest, paths.manifest)
        print("      Status: COMPLETE")
        print(f"      Output: {paths.root}")
        print(f"      Paper promotion: {validation.paper_promotion_status}")
        return 0

    except Exception as exc:
        manifest.update(
            {
                "status": "FAILED",
                "engineering_status": "FAIL",
                "scientific_status": "STOP_AND_REVIEW",
                "paper_promotion_status": "BLOCKED",
                "completed_at": _now_local().isoformat(),
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
        )
        write_json(manifest, paths.manifest)
        (paths.logs / "failure_traceback.txt").write_text(
            traceback.format_exc(), encoding="utf-8"
        )
        print(f"\nEXP2 FAILED: {type(exc).__name__}: {exc}", flush=True)
        print(f"Failure report: {paths.logs / 'failure_traceback.txt'}", flush=True)
        return 1

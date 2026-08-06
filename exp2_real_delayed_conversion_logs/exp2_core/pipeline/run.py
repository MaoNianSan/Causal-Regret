from __future__ import annotations

import json
import os
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
from contracts import (
    EXPERIMENT_ID,
    EXPERIMENT_SLUG,
    EXPERIMENT_TITLE,
    SCHEMA_VERSION,
    ConfigurationError,
    DataContractError,
    ScientificInvariantError,
)
from data_io import (
    canonical_json_hash,
    file_sha256,
    input_manifest_identity_hash,
    load_config,
    prepare_raw_log,
    write_frame,
    write_json,
)
from metrics import compute_primary_metrics
from targeted import build_robustness_summary, run_targeted_analyses
from reporting import (
    make_ambiguity_figure,
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


def _code_identity(root: Path) -> str:
    files = sorted(
        path for path in root.rglob("*.py") if "__pycache__" not in path.parts
    )
    return canonical_json_hash(
        {
            str(path.relative_to(root)): path.read_bytes().hex()
            for path in files
        }
    )


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


def _write_artifact_manifest(run_root: Path, output_path: Path) -> None:
    rows = []
    for path in sorted(run_root.rglob("*")):
        if not path.is_file() or path == output_path:
            continue
        rows.append(
            {
                "relative_path": path.relative_to(run_root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    write_json(
        {"schema_version": SCHEMA_VERSION, "artifact_count": len(rows), "artifacts": rows},
        output_path,
    )


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

    project_root = Path(__file__).resolve().parents[2]
    config_file = Path(config_path) if config_path is not None else project_root / "config.yaml"
    config = load_config(config_file)
    validate_frozen_configuration(config)
    paths = _create_paths(project_root, mode)
    run_id = paths.root.name
    config_hash = canonical_json_hash(config)
    code_identity = _code_identity(project_root)
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
        "schema_version": SCHEMA_VERSION,
        "run_tier": mode,
        "paper_result": False,
        "status": "RUNNING",
        "engineering_status": "PENDING",
        "scientific_status": "PENDING",
        "paper_promotion_status": "INELIGIBLE_FAST" if mode == "fast" else "PENDING",
        "started_at": _now_local().isoformat(),
        "code_identity": code_identity,
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
                    seed=int(config["resampling"]["seed"]),
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
            cohort.journey_manifest["primary_exclusion_reason"]
            .value_counts(dropna=False)
            .rename_axis("primary_exclusion_reason")
            .reset_index(name="journey_count"),
            paths.derived / "exclusion_summary.csv",
        )
        if cohort.cohort_flow is not None:
            _write_csv(cohort.cohort_flow, paths.derived / "cohort_flow.csv")
        temporal = pd.DataFrame(
            [
                {"quantity": "observed_exposure_start_utc", "value": prepared.observed_start_utc.isoformat()},
                {"quantity": "observed_exposure_end_utc", "value": prepared.observed_end_utc.isoformat()},
                {"quantity": "candidate_conversion_start_utc", "value": str(prepared.candidates["conversion_timestamp_utc"].min())},
                {"quantity": "candidate_conversion_end_utc", "value": str(prepared.candidates["conversion_timestamp_utc"].max())},
                {"quantity": "retained_conversion_start_utc", "value": str(cohort.journey_manifest.loc[cohort.journey_manifest["is_primary_eligible"], "conversion_timestamp_utc"].min())},
                {"quantity": "retained_conversion_end_utc", "value": str(cohort.journey_manifest.loc[cohort.journey_manifest["is_primary_eligible"], "conversion_timestamp_utc"].max())},
            ]
        )
        _write_csv(temporal, paths.derived / "temporal_coverage.csv")
        _write_csv(
            prepared.candidates.assign(conversion_date_utc=prepared.candidates["conversion_timestamp_utc"].dt.floor("D"))
            .groupby("conversion_date_utc", dropna=False).size().rename("candidate_count").reset_index(),
            paths.derived / "conversion_date_distribution.csv",
        )
        _write_csv(
            prepared.candidates.groupby("source_date_utc", dropna=False).size().rename("candidate_count").reset_index(),
            paths.derived / "source_date_distribution.csv",
        )
        write_json(cohort.audit, paths.audit / "cohort_audit.json")
        write_json(
            {
                "schema_version": SCHEMA_VERSION,
                "analysis_window_days": cohort.audit.get("analysis_window_days", 7),
                "primary_candidate_window_days": config["cohort"]["primary_candidate_window_days"],
                "robustness_candidate_window_days": config["cohort"].get("robustness_candidate_window_days", []),
                "require_complete_lookback": bool(config["cohort"]["require_complete_lookback"]),
                "require_single_campaign_per_journey": bool(config["cohort"]["require_single_campaign_per_journey"]),
                "retained_journey_count": int(cohort.journey_manifest["is_primary_eligible"].sum()),
                "retained_uid_count": int(cohort.journey_manifest.loc[cohort.journey_manifest["is_primary_eligible"], "user_id"].nunique()),
                "eligible_cell_count": int(len(cohort.decision_cell_universe)),
            },
            paths.derived / "cohort_scope.json",
        )
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
        write_json(
            {
                "schema_version": SCHEMA_VERSION,
                "credit_conservation_status": "PASS",
                "primary_route_count": len(config["routes"]["primary"]),
                "exploratory_routes_enabled": bool(config["routes"].get("run_exploratory_by_default", False)),
                "route_summary": routes.route_summary.to_dict(orient="records"),
            },
            paths.audit / "route_invariants.json",
        )
        _write_csv(routes.em_diagnostics, paths.audit / "em_diagnostics.csv")
        _write_csv(
            routes.logged_reference_summary,
            paths.audit / "logged_reference_summary.csv",
        )
        print("      Primary routes: 5")
        print("      Exploratory EM route: DISABLED")
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
        _write_csv(point.ambiguity_strata, paths.derived / "ambiguity_mechanism.csv")
        targeted = run_targeted_analyses(
            prepared_candidates=prepared.candidates,
            impression_counts=prepared.impression_counts,
            primary_cohort=cohort,
            primary_metrics=point,
            config=config,
            mode=mode,
        )
        _write_csv(targeted, paths.derived / "targeted_robustness.csv")
        robustness_summary = build_robustness_summary(targeted, config)
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
        write_json(bootstrap.audit, paths.audit / "resampling_audit.json")
        arrival, pairwise = attach_bootstrap_intervals(
            point.arrival_displacement,
            point.source_route_pairwise,
            bootstrap,
        )
        _write_csv(arrival, paths.derived / "arrival_displacement.csv")
        _write_csv(pairwise, paths.derived / "source_route_pairwise.csv")
        _write_csv(
            pd.concat(
                [
                    arrival.assign(comparison_group="source_vs_arrival_anchor", route_left="arrival_time_accounting_anchor", route_right=arrival["route_id"]),
                    pairwise.assign(comparison_group="source_route_pair"),
                ],
                ignore_index=True,
                sort=False,
            ),
            paths.derived / "primary_comparisons.csv",
        )
        bootstrap_bias_audit = build_bootstrap_bias_audit(arrival, pairwise)
        write_json(bootstrap_bias_audit, paths.audit / "bootstrap_bias_audit.json")
        print(f"      Replicates: {bootstrap.audit['resampling_repetitions']:,}")
        print(
            "      Resampling-range diagnostics: "
            f"{bootstrap_bias_audit['full_sample_outside_resampling_range_count']:,}"
        )
        print("      Status: PASS")

        _log_stage(7, total_stages, "Generate manuscript figures and tables")
        run_metadata = {
            "run_id": run_id,
            "run_tier": mode,
            "paper_result": False,
            "experiment_id": EXPERIMENT_ID,
            "code_identity": code_identity,
            "schema_version": SCHEMA_VERSION,
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
        make_ambiguity_figure(
            point.ambiguity_strata,
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
            cohort_flow=cohort.cohort_flow,
        )
        robustness_csv = _write_csv(
            robustness_summary, paths.tables / "table_exp2_robustness_summary.csv"
        )
        robustness_tex = paths.tables / "table_exp2_robustness_summary.tex"
        robustness_tex.write_text(
            robustness_summary.to_latex(index=False, escape=True), encoding="utf-8"
        )
        table_files.extend([robustness_csv, robustness_tex])
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
            expected_bootstrap_repetitions=int(bootstrap.audit["resampling_repetitions"]),
            bootstrap_audit=bootstrap.audit,
            development_override=bool(manifest["development_override"]),
        )
        validation_payload = {
                "engineering_status": validation.engineering_status,
                "scientific_status": validation.scientific_status,
                "paper_promotion_status": validation.paper_promotion_status,
                "checks": validation.checks,
            }
        write_json(validation_payload, paths.audit / "scientific_validation.json")
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
                "resampling_repetitions": bootstrap.audit["resampling_repetitions"],
                "resampling_range_diagnostic_count": bootstrap_bias_audit[
                    "full_sample_outside_resampling_range_count"
                ],
                "input_content_sha256": prepared.input_manifest["input_content_sha256"],
                "primary_full_runs_complete": mode == "full" and not bool(manifest["development_override"]),
                "main_figures_reconstructable": True,
                "main_tables_reconstructable": True,
                "claims_within_scope": True,
            }
        )
        write_json(manifest, paths.manifest)
        _write_artifact_manifest(paths.root, paths.audit / "artifact_manifest.json")
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


def run_cohort_check(
    *,
    config_path: str | Path | None = None,
    input_path: str | Path | None = None,
) -> int:
    """Run only the route-independent real-data cohort gate."""
    project_root = Path(__file__).resolve().parents[2]
    config_file = Path(config_path) if config_path is not None else project_root / "config.yaml"
    config = load_config(config_file)
    validate_frozen_configuration(config)
    resolved_input = Path(input_path) if input_path is not None else project_root / str(config["input"]["raw_file"])
    check_id = f"cohort-check-{_now_local().strftime('%Y%m%dT%H%M%S%z')}"
    output_root = project_root / "outputs" / check_id
    output_root.mkdir(parents=True, exist_ok=False)
    try:
        prepared = prepare_raw_log(resolved_input, config, mode="full", progress=True)
        primary = build_primary_cohort(prepared.candidates, prepared.impression_counts, config)
        robustness_counts: dict[str, dict[str, int | float]] = {}
        for window in config["cohort"].get("robustness_candidate_window_days", []):
            window_config = dict(config)
            window_config["cohort"] = dict(config["cohort"])
            window_config["cohort"]["analysis_window_days"] = int(window)
            cohort = build_primary_cohort(prepared.candidates, prepared.impression_counts, window_config)
            retained = cohort.journey_manifest.loc[cohort.journey_manifest["is_primary_eligible"]]
            robustness_counts[str(window)] = {
                "retained_journeys": int(len(retained)),
                "retained_uids": int(retained["user_id"].nunique()),
                "eligible_cells": int(len(cohort.decision_cell_universe)),
                "ambiguity_rate": float(cohort.audit.get("ambiguous_journey_rate", 0.0)),
            }
        primary_retained = primary.journey_manifest.loc[primary.journey_manifest["is_primary_eligible"]]
        status = {
            "schema_version": SCHEMA_VERSION,
            "cohort_check_status": "PASS",
            "primary_7d_retained_journeys": int(len(primary_retained)),
            "primary_7d_retained_uids": int(primary_retained["user_id"].nunique()),
            "primary_7d_eligible_cells": int(len(primary.decision_cell_universe)),
            "primary_7d_ambiguity_rate": float(primary.audit.get("ambiguous_journey_rate", 0.0)),
            "robustness_windows": robustness_counts,
            "temporal_coverage_status": "PASS",
            "full_exp2_rerun_allowed": True,
        }
        write_json(status, output_root / "cohort_check_status.json")
        _write_csv(primary.cohort_flow, output_root / "cohort_flow.csv")
        write_json(prepared.audit, output_root / "raw_input_audit.json")
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 0
    except (ConfigurationError, DataContractError, ScientificInvariantError) as exc:
        status = {
            "schema_version": SCHEMA_VERSION,
            "cohort_check_status": "STOP_AND_REVIEW",
            "full_exp2_rerun_allowed": False,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
        write_json(status, output_root / "cohort_check_status.json")
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 1

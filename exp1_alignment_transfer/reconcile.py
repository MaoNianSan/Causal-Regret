"""Selective Exp1 rebuilds that reuse a verified scientific source run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from config import RUN
from main import OUTPUTS_DIR, PROJECT_ROOT
from plot_appendix import generate_all as generate_appendix_figures
from plot_main import generate as generate_main_figure
from self_check import run_checks
from src.artifact_io import read_frame, refresh_output_manifest
from src.derived import generate_all_derived
from src.run_provenance import (
    Exp1ReuseDecision,
    audit_exp1_provenance,
    bootstrap_existing_full_provenance,
    record_exp1_reconciliation,
)


def _run_tier_for(source_run: Path) -> str:
    try:
        relative = source_run.resolve().relative_to(OUTPUTS_DIR.resolve())
    except ValueError as exc:
        raise RuntimeError("source run must be inside exp1_alignment_transfer/outputs") from exc
    if len(relative.parts) != 1 or relative.name not in {"fast", "full"}:
        raise RuntimeError("source run must be outputs/fast or outputs/full")
    return relative.name


def _rebuild_aggregation(source_run: Path, run_tier: str) -> None:
    route_seed = read_frame(source_run / "seed_metrics" / "exp1_route_seed_metrics.parquet")
    learner_seed = read_frame(source_run / "seed_metrics" / "exp1_learner_seed_metrics.parquet")
    delay_round = read_frame(source_run / "raw" / "exp1_delay_source_rounds.parquet")
    route_path = source_run / "raw" / "exp1_route_diagnostic_rounds.parquet"
    if route_path.exists():
        route_round = pd.read_parquet(
            route_path,
            filters=[
                ("route_id", "==", "arrival_assigned"),
                ("mechanism_id", "in", ["exact_valid_shift", "systematic_misbinding"]),
            ],
        )
    else:
        route_round = read_frame(route_path)
        route_round = route_round[
            (route_round.route_id == "arrival_assigned")
            & route_round.mechanism_id.isin(
                ["exact_valid_shift", "systematic_misbinding"]
            )
        ].copy()
    repetitions = (
        RUN.bootstrap_repetitions_fast
        if run_tier == "fast"
        else RUN.bootstrap_repetitions_full
    )
    generate_all_derived(
        source_run,
        route_seed=route_seed,
        learner_seed=learner_seed,
        delay_round=delay_round,
        route_round=route_round,
        repetitions=repetitions,
        ci_level=RUN.ci_level,
    )


def _rebuild_reporting(source_run: Path, run_tier: str) -> None:
    del source_run  # Figure entry points resolve the canonical tier directory.
    generate_main_figure(run_tier)
    generate_appendix_figures(run_tier)


def reconcile(source_run: Path, rebuild: str) -> dict[str, object]:
    run_tier = _run_tier_for(source_run)
    before = audit_exp1_provenance(source_run, PROJECT_ROOT)
    if not before["scientific_reuse_eligible"]:
        raise RuntimeError(
            "Exp1 selective rebuild refused: " + str(before["failure_reason"])
        )

    required = before["decision"]
    if rebuild == "reporting" and required == Exp1ReuseDecision.DOWNSTREAM_REBUILD.value:
        raise RuntimeError("Validation or aggregation is stale; use --rebuild downstream")
    if rebuild == "validation" and required == Exp1ReuseDecision.DOWNSTREAM_REBUILD.value:
        if not before["stage_hash_matches"]["aggregation_source_hash"]:
            raise RuntimeError("Aggregation is stale; use --rebuild aggregation or downstream")

    rebuilt: list[str] = []
    if rebuild in {"aggregation", "downstream"}:
        _rebuild_aggregation(source_run, run_tier)
        rebuilt.append("aggregation")
    if rebuild in {"validation", "aggregation", "downstream"}:
        run_checks(run_tier)
        rebuilt.append("validation")
    if rebuild in {"reporting", "downstream"}:
        _rebuild_reporting(source_run, run_tier)
        rebuilt.append("reporting")

    reconciliation = record_exp1_reconciliation(source_run, PROJECT_ROOT, rebuilt)
    refresh_output_manifest(source_run)
    after = audit_exp1_provenance(source_run, PROJECT_ROOT)
    return {
        "source_run": str(source_run),
        "rebuilt_stages": rebuilt,
        "reconciliation": str(reconciliation),
        "before": before,
        "after": after,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild Exp1 downstream artifacts without rerunning simulation."
    )
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument(
        "--rebuild",
        choices=("validation", "aggregation", "reporting", "downstream"),
        default=None,
    )
    parser.add_argument(
        "--initialize-existing",
        action="store_true",
        help="write explicit historical provenance for a verified existing full run",
    )
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    source_run = args.source_run.resolve()
    _run_tier_for(source_run)

    if args.initialize_existing:
        lineage, stage = bootstrap_existing_full_provenance(source_run, PROJECT_ROOT)
        print(f"EXP1_PROVENANCE_INITIALIZED lineage={lineage} stage={stage}")
    if args.audit:
        print(json.dumps(audit_exp1_provenance(source_run, PROJECT_ROOT), indent=2))
    if args.rebuild:
        print(json.dumps(reconcile(source_run, args.rebuild), indent=2))
    if not any((args.initialize_existing, args.audit, args.rebuild)):
        parser.error("provide --initialize-existing, --audit, and/or --rebuild")


if __name__ == "__main__":
    main()

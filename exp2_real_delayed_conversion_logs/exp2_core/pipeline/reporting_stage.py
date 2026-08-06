from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contracts import EXPERIMENT_ID, SCHEMA_VERSION

from ..cohort import CohortBuildResult
from ..raw_data import PreparedRawData, canonical_json_hash, input_manifest_identity_hash
from ..reporting import (
    make_ambiguity_figure,
    make_delay_composition_figure,
    make_main_figure,
    make_pairwise_appendix_figure,
    make_tables,
)
from .context import RunContext, now_local, write_csv
from .metric_stage import MetricStageResult
from .resampling_stage import ResamplingStageResult


@dataclass(frozen=True)
class ReportingStageResult:
    run_metadata: dict[str, Any]
    table_files: tuple[Path, ...]


def run_reporting_stage(
    context: RunContext,
    prepared: PreparedRawData,
    cohort: CohortBuildResult,
    metrics: MetricStageResult,
    resampling: ResamplingStageResult,
) -> ReportingStageResult:
    run_metadata = {
        "run_id": context.run_id,
        "run_tier": context.mode,
        "paper_result": False,
        "experiment_id": EXPERIMENT_ID,
        "code_identity": context.code_identity,
        "schema_version": SCHEMA_VERSION,
        "config_hash": context.config_hash,
        "input_manifest_hash": input_manifest_identity_hash(prepared.input_manifest),
        "cohort_hash": canonical_json_hash(
            sorted(cohort.journey_manifest.loc[cohort.journey_manifest["is_primary_eligible"], "journey_id"].astype(str))
        ),
        "decision_cell_universe_hash": canonical_json_hash(
            sorted(cohort.decision_cell_universe["decision_cell_id"].astype(str))
        ),
        "generated_at": now_local().isoformat(),
    }
    make_main_figure(resampling.arrival, resampling.pairwise, context.paths.figures, context.config, run_metadata=run_metadata)
    make_pairwise_appendix_figure(resampling.pairwise, context.paths.figures, context.config, run_metadata=run_metadata)
    make_ambiguity_figure(metrics.point.ambiguity_strata, context.paths.figures, context.config, run_metadata=run_metadata)
    make_delay_composition_figure(cohort.eligible_candidates, context.paths.figures, context.config, run_metadata=run_metadata)
    table_files = make_tables(
        cohort.cohort_summary,
        resampling.arrival,
        resampling.pairwise,
        context.paths.tables,
        bootstrap_audit=resampling.bootstrap.audit,
        cohort_flow=cohort.cohort_flow,
    )
    robustness_csv = write_csv(metrics.robustness_summary, context.paths.tables / "table_exp2_robustness_summary.csv")
    robustness_tex = context.paths.tables / "table_exp2_robustness_summary.tex"
    robustness_tex.write_text(metrics.robustness_summary.to_latex(index=False, escape=True), encoding="utf-8")
    table_files.extend([robustness_csv, robustness_tex])
    print(f"      Figures: {len(list(context.paths.figures.glob('*.pdf')))} PDF")
    print(f"      Tables: {len(table_files)} files")
    print("      Status: PASS")
    return ReportingStageResult(run_metadata=run_metadata, table_files=tuple(table_files))

"""Read-only registry of frozen source artifacts for CR-EXP-OUTPUT-V1."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from presentation import SPEC_ID
from presentation.common import sanitize_run_id

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class PresentationSource:
    experiment: str
    experiment_id: str
    run_id: str
    source_run: Path
    scientific_source_paper_result: bool
    run_tier: str
    result_schema: str
    config_hash: str
    required_files: tuple[str, ...]
    main_figure_id: str

    def resolved(self) -> "PresentationSource":
        return PresentationSource(
            **{**self.__dict__, "source_run": self.source_run.resolve()}
        )

    def required_paths(self) -> tuple[Path, ...]:
        base = self.source_run
        return tuple(base / rel for rel in self.required_files)

    def missing_files(self) -> list[Path]:
        return [path for path in self.required_paths() if not path.exists()]

    def as_plan(self, preview_root: Path) -> dict[str, object]:
        safe = sanitize_run_id(self.run_id)
        return {
            "spec_id": SPEC_ID,
            "experiment": self.experiment,
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "run_tier": self.run_tier,
            "scientific_source_paper_result": self.scientific_source_paper_result,
            "result_schema": self.result_schema,
            "config_hash": self.config_hash,
            "source_run": str(self.source_run),
            "expected_preview_directory": str(preview_root / self.experiment_id / safe / SPEC_ID),
            "required_source_files": [str(p) for p in self.required_paths()],
            "missing_source_files": [str(p) for p in self.missing_files()],
            "main_figure_id": self.main_figure_id,
        }


SOURCES: dict[str, PresentationSource] = {
    "1": PresentationSource(
        experiment="Exp1", experiment_id="exp1_alignment_transfer",
        run_id="exp1_alignment_transfer:full:2026-08-17T06:28:21.157011+00:00",
        source_run=ROOT / "exp1_alignment_transfer" / "outputs" / "full",
        scientific_source_paper_result=False, run_tier="full", result_schema="exp1_alignment_transfer_v1",
        config_hash="483df70d6daceef6ffbb42b5c59d98e50373a606a8d9d6e9da8f317eee8af914",
        required_files=(
            "figures/data/fig_exp1_alignment_transfer_data.csv",
            "figures/data/fig_exp1_delay_survival_data.csv",
            "figures/data/fig_exp1_state_coupling_data.csv",
            "figures/data/fig_exp1_reversal_margin_data.csv",
            "figures/data/fig_exp1_route_trajectory_data.csv",
            "tables/tab_exp1_mechanism_summary.csv",
            "metadata/artifact_manifest.json", "metadata/exp1_run_lineage.json",
        ), main_figure_id="fig_exp1_alignment_transfer",
    ),
    "2": PresentationSource(
        experiment="Exp2", experiment_id="exp2_real_delayed_conversion_logs",
        run_id="exp2-full-20260807T111616+0800",
        source_run=ROOT / "exp2_real_delayed_conversion_logs" / "outputs" / "paper" / "exp2-full-20260807T111616+0800",
        scientific_source_paper_result=True, run_tier="paper", result_schema="exp2_attribution_sensitivity_v2",
        config_hash="bc6143ea17e219a7bb625a522c770ba83ea2430aca8e5f3773467a10f295e102",
        required_files=(
            "figures/figure_exp2_attribution_sensitivity_source.csv",
            "figures/figure_exp2_ambiguity_mechanism_source.csv",
            "figures/figure_exp2_delay_appendix_data.csv",
            "figures/figure_exp2_pairwise_appendix_data.csv",
            "tables/table_exp2_cohort_flow.csv",
            "tables/table_exp2_pairwise_appendix.csv",
            "tables/table_exp2_robustness_summary.csv",
            "derived/ambiguity_mechanism.csv", "derived/targeted_robustness.csv",
            "run_manifest.json",
        ), main_figure_id="figure_exp2_attribution_sensitivity",
    ),
    "3": PresentationSource(
        experiment="Exp3", experiment_id="exp3_sequential_recommendation_delayed_feedback",
        run_id="exp3-full-20260807T072340Z",
        source_run=ROOT / "exp3_sequential_recommendation_delayed_feedback" / "paper_candidate",
        scientific_source_paper_result=True, run_tier="full", result_schema="exp3_paper_candidate",
        config_hash="2eebb3dfafa708ac36ff5b5fb2d215b77f5189e37ae94ea9afe8470831770580",
        required_files=(
            "tables/exp3_primary_route_results.csv",
            "tables/exp3_support_coverage.csv",
            "tables/exp3_action_space_coverage.csv",
            "tables/exp3_paired_ranking_contrast.csv",
            "tables/exp3_ridge_history_cv.csv", "tables/exp3_ridge_coefficients.csv",
            "tables/exp3_resampling_structure_diagnostics.csv",
            "tables/exp3_full_design_support_preflight.csv",
            "tables/exp3_data_dependence_structure.csv",
            "tables/exp3_decile_calibration.csv",
            "figures/data/exp3_main_score_gap_ranking_data.csv", "manifest.json",
        ), main_figure_id="exp3_main_score_gap_ranking",
    ),
    "4": PresentationSource(
        experiment="Exp4", experiment_id="exp4_controlled_route_audit",
        run_id="full_20260817T071019Z_7d7146b7",
        source_run=ROOT / "exp4_controlled_route_audit" / "outputs" / "runs" / "full_20260817T071019Z_7d7146b7",
        scientific_source_paper_result=False, run_tier="full", result_schema="exp4_controlled_route_audit_v3",
        config_hash="9a0a87ecc64ead7528cbd43d299e26c64ea849f9d54852e0cc45d7e061364a7",
        required_files=(
            "derived/module_a/exp4_module_a_population_summary.csv",
            "derived/module_b/exp4_module_b_audit_performance.csv",
            "derived/module_b/exp4_module_b_weight_diagnostics.csv",
            "derived/module_c/exp4_module_c_control_summary.csv",
            "derived/module_c/exp4_module_c_correspondence_checks.csv",
            "derived/module_c/exp4_module_c_parameter_recovery.csv",
            "figures/data/fig_app_exp4_route_optimal_set_conflict_data.csv",
            "figures/data/fig_app_exp4_smooth_loss_robustness_data.csv",
            "figures/data/fig_app_exp4_effective_support_data.csv",
            "tables/tbl_app_exp4_parameters.csv",
            "tables/tbl_app_exp4_paired_contrasts.csv",
            "tables/tbl_app_exp4_audit_performance.csv",
            "tables/tbl_exp4_calibration_controls.csv",
            "logs/run_config.json", "logs/stages/reporting.json",
            "logs/exp4_stage_config_migration.json", "logs/exp4_stage_hash_migration.json",
        ), main_figure_id="fig_exp4_route_alignment_and_audit_reliability",
    ),
}


def get_source(exp: str) -> PresentationSource:
    key = str(exp).removeprefix("exp").removeprefix("EXP")
    if key not in SOURCES:
        raise KeyError(f"Unknown experiment {exp!r}; expected 1, 2, 3, or 4")
    source = SOURCES[key].resolved()
    missing = source.missing_files()
    if missing:
        raise FileNotFoundError("Missing frozen presentation source files: " + ", ".join(map(str, missing)))
    return source


def iter_sources(exp: str) -> Iterable[PresentationSource]:
    if str(exp).lower() == "all":
        return [get_source(key) for key in ("1", "2", "3", "4")]
    return [get_source(exp)]


def load_run_manifest(source: PresentationSource) -> dict[str, object]:
    candidates = (source.source_run / "run_manifest.json", source.source_run / "manifest.json", source.source_run / "logs" / "run_config.json")
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return {}

from __future__ import annotations

"""Static view of the required EXP1 artifact bundle.

The runner remains the source of truth.  This module exists for lightweight
inspection tools and mirrors the manifest contract used by ``self_check.py``.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactSpec:
    logical_name: str
    relative_path: str
    required: bool = True


_BASE = (
    ArtifactSpec("run_manifest", "metadata/run_manifest.json"),
    ArtifactSpec("design_manifest", "metadata/design_manifest.csv"),
    ArtifactSpec("scenario_trace_manifest", "metadata/scenario_trace_manifest.csv"),
    ArtifactSpec("seed_level_results", "raw/seed_level_results.csv"),
    ArtifactSpec("selected_trajectory_points", "processed/selected_trajectory_points.csv"),
    ArtifactSpec("seed_summary", "summaries/seed_summary.csv"),
    ArtifactSpec("method_summary", "summaries/method_summary.csv"),
    ArtifactSpec("diagnostic_summary", "summaries/diagnostic_summary.csv"),
    ArtifactSpec("paired_tests", "summaries/paired_tests.csv"),
    ArtifactSpec("bootstrap_ci", "summaries/bootstrap_ci.csv"),
    ArtifactSpec("matched_mean_delay_summary", "summaries/matched_mean_delay_summary.csv"),
    ArtifactSpec("results_table", "tables/table_exp1_results.csv"),
    ArtifactSpec("diagnostics_table", "tables/table_exp1_diagnostics.csv"),
    ArtifactSpec("matched_delay_table", "tables/table_exp1_matched_delay.csv"),
)

_FIGURES = (
    "fig_exp1_validity_boundary",
    "fig_exp1_same_mean_delay",
    "fig_exp1_attribution_diagnostics",
    "fig_exp1_proxy_quality",
    "fig_app_exp1_selected_trajectories",
    "fig_app_exp1_mismatch_diagnostics",
)

ARTIFACTS = _BASE + tuple(
    artifact
    for figure_id in _FIGURES
    for artifact in (
        ArtifactSpec(f"{figure_id}_data", f"figures/data/{figure_id}_data.csv"),
        ArtifactSpec(f"{figure_id}_metadata", f"figures/metadata/{figure_id}_metadata.json"),
        ArtifactSpec(f"{figure_id}_pdf", f"figures/pdf/{figure_id}.pdf"),
        ArtifactSpec(f"{figure_id}_png", f"figures/png/{figure_id}.png"),
    )
)

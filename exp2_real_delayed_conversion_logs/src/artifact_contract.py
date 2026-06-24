from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactSpec:
    name: str
    relative_path: str
    required: bool = True


ARTIFACTS = (
    ArtifactSpec("run_status", "metadata/run_status.json"),
    ArtifactSpec(
        "route_sensitivity_summary", "summaries/exp2_route_sensitivity_summary.csv"
    ),
    ArtifactSpec("pairwise_top_k_overlap", "summaries/exp2_pairwise_top_k_overlap.csv"),
    ArtifactSpec(
        "main_figure_data", "figures/data/fig_exp2_attribution_sensitivity_data.csv"
    ),
    ArtifactSpec(
        "appendix_pairwise_figure_data",
        "figures/data/fig_app_exp2_source_route_pairwise_overlap_data.csv",
    ),
    ArtifactSpec("self_check", "checks/exp2_self_check_results.csv"),
)

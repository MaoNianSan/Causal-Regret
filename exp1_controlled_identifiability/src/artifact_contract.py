from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactSpec:
    logical_name: str
    relative_path: str
    required: bool = True


ARTIFACTS = (
    ArtifactSpec("run_manifest", "metadata/run_manifest.json"),
    ArtifactSpec("design_manifest", "metadata/design_manifest.csv"),
    ArtifactSpec("scenario_trace_manifest", "metadata/scenario_trace_manifest.csv"),
    ArtifactSpec("seed_summary", "summaries/seed_summary.csv"),
    ArtifactSpec("validity_data", "figures/data/fig_exp1_validity_boundary_data.csv"),
    ArtifactSpec("matched_delay_data", "figures/data/fig_exp1_same_mean_delay_data.csv"),
    ArtifactSpec("attribution_data", "figures/data/fig_exp1_attribution_diagnostics_data.csv"),
    ArtifactSpec("proxy_quality_data", "figures/data/fig_exp1_proxy_quality_data.csv"),
)

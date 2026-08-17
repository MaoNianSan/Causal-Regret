"""Concise run summary with scientific scope and execution boundaries."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def write_run_summary(run_dir: Path) -> None:
    run_config = json.loads((run_dir / "logs" / "run_config.json").read_text(encoding="utf-8"))
    engineering = json.loads((run_dir / "checks" / "exp4_engineering_checks.json").read_text(encoding="utf-8"))
    scientific = json.loads((run_dir / "checks" / "exp4_scientific_checks.json").read_text(encoding="utf-8"))
    boundary = pd.read_csv(run_dir / "derived" / "module_a" / "exp4_module_a_population_summary.csv")
    performance = pd.read_csv(run_dir / "derived" / "module_b" / "exp4_module_b_audit_performance.csv")
    controls = pd.read_csv(run_dir / "derived" / "module_c" / "exp4_module_c_control_summary.csv")
    q1 = boundary[(boundary["route_id"] == "proxy_label") & np.isclose(boundary["route_label_rate"], 1.0)]
    lineage = _load_lineage(run_dir)
    stage_record = _load_stage_record(run_dir)
    lines = [
        "# Experiment 4 v3 Run Summary",
        "",
        f"- Run ID: `{run_config['run_id']}`",
        f"- Run tier: `{run_config['run_tier']}`",
        f"- Result schema: `{run_config['result_schema']}`",
        f"- Engineering status: `{engineering['status']}`",
        f"- Scientific status: `{scientific['status']}`",
        "- Paper promotion: `NOT_RUN`",
        "- Paper result: `false`",
        "",
        "## Run lineage",
        "",
        f"- Lineage schema: `{lineage.get('schema', 'MISSING')}`",
        f"- Simulation execution mode: `{lineage.get('simulation_execution_mode', 'UNKNOWN')}`",
        f"- Simulation source run: `{lineage.get('simulation_source_run_id') or 'NONE'}`",
        f"- Downstream execution mode: `{lineage.get('downstream_execution_mode', 'UNKNOWN')}`",
        f"- Downstream source run: `{lineage.get('downstream_source_run_id') or 'NONE'}`",
        f"- Created from commit: `{lineage.get('created_from_commit', 'UNKNOWN')}`",
        f"- Exp4 worktree clean at start: `{lineage.get('exp4_worktree_clean_at_start', False)}`",
        f"- Formal Full clean-worktree required: `{run_config.get('formal_full_clean_worktree_required', False)}`",
        f"- Source unchanged during run: `{stage_record.get('source_unchanged_during_run', False) if stage_record else False}`",
        "",
        "## Core diagnostics",
        "",
        f"- Maximum q_route=1 mean pairwise gap discrepancy: {q1['mean_pairwise_gap_discrepancy_mean'].abs().max():.3e}",
        f"- Maximum q_route=1 mean round-max gap defect (legacy v2): {q1['population_action_gap_defect_mean'].abs().max():.3e}",
        f"- Audit bias range: [{performance['bias'].min():.4f}, {performance['bias'].max():.4f}]",
        f"- Audit RMSE range: [{performance['rmse'].min():.4f}, {performance['rmse'].max():.4f}]",
        f"- Module C estimability range: [{controls['estimability_rate'].min():.3f}, {controls['estimability_rate'].max():.3f}]",
        "",
        "## Interpretation boundary",
        "",
        "- Module A estimates a controlled population route-alignment boundary; the v3 primary estimand is the pair-average gap discrepancy D_pair.",
        "- Module B separates the pair-average population discrepancy from finite/selective audit reliability; all audit designs target the same d_i_pair.",
        "- Module C evaluates discrepancy reduction inside a prespecified affine family; it does not create a corrected policy or certify route validity.",
        "- Known simulated IPW probabilities do not establish validity under an unknown real-world inclusion mechanism.",
        "",
        "FULL_RUN_EXECUTED=NO" if run_config["run_tier"] != "full" else "FULL_RUN_EXECUTED=YES",
        "PAPER_PROMOTION_EXECUTED=NO",
        "GIT_COMMIT_EXECUTED=NO",
        "GIT_PUSH_EXECUTED=NO",
    ]
    (run_dir / "reports" / "exp4_run_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def _load_lineage(run_dir: Path) -> dict[str, object]:
    from exp4.outputs.run_lineage import RUN_LINEAGE_SCHEMA, load_run_lineage

    lineage = load_run_lineage(run_dir)
    if lineage is None:
        return {}
    return {"schema": RUN_LINEAGE_SCHEMA, **lineage.as_dict()}


def _load_stage_record(run_dir: Path) -> dict[str, object] | None:
    from exp4.validation.run_provenance import load_stage_provenance_record

    return load_stage_provenance_record(run_dir)

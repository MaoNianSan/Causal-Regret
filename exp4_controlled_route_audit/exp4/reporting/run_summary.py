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
    lines = [
        "# Experiment 4 v2 Run Summary",
        "",
        f"- Run ID: `{run_config['run_id']}`",
        f"- Run tier: `{run_config['run_tier']}`",
        f"- Result schema: `{run_config['result_schema']}`",
        f"- Engineering status: `{engineering['status']}`",
        f"- Scientific status: `{scientific['status']}`",
        "- Paper promotion: `NOT_RUN`",
        "- Paper result: `false`",
        "",
        "## Core diagnostics",
        "",
        f"- Maximum q_route=1 population defect: {q1['population_action_gap_defect_mean'].abs().max():.3e}",
        f"- Audit bias range: [{performance['bias'].min():.4f}, {performance['bias'].max():.4f}]",
        f"- Audit RMSE range: [{performance['rmse'].min():.4f}, {performance['rmse'].max():.4f}]",
        f"- Module C estimability range: [{controls['estimability_rate'].min():.3f}, {controls['estimability_rate'].max():.3f}]",
        "",
        "## Interpretation boundary",
        "",
        "- Module A estimates a controlled population route-alignment boundary.",
        "- Module B separates population defect from finite/selective audit reliability.",
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

"""Generate a structured Chinese run summary for Exp4."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import config


def run(run_dir: Path) -> None:
    run_config = json.loads(
        (run_dir / "logs" / "run_config.json").read_text(encoding="utf-8")
    )
    boundary = pd.read_csv(run_dir / "derived" / "exp4_route_boundary_summary.csv")
    audit = pd.read_csv(run_dir / "derived" / "exp4_audit_condition_summary.csv")
    controls = pd.read_csv(run_dir / "derived" / "exp4_calibration_control_summary.csv")
    engineering = json.loads(
        (run_dir / "checks" / "exp4_self_check.json").read_text(encoding="utf-8")
    )
    scientific = json.loads(
        (run_dir / "checks" / "exp4_scientific_check.json").read_text(encoding="utf-8")
    )
    primary_boundary = boundary[
        (boundary["route_id"] == "proxy_label")
        & (boundary["analysis_tier"] == "primary")
    ].copy()
    q1_max = primary_boundary[
        np.isclose(primary_boundary["route_label_rate"], 1.0)
    ]["population_raw_action_gap_defect_mean"].abs().max()
    proxy_audit = audit[audit["route_id"] == "proxy_label"].copy()
    biased_rows = proxy_audit[
        (proxy_audit["audit_design_id"] == "ambiguity_biased_unweighted")
        & (proxy_audit["audit_evidence_rate"] < 1.0)
    ]
    ipw_rows = proxy_audit[
        (proxy_audit["audit_design_id"] == "ambiguity_biased_ipw")
        & (proxy_audit["audit_evidence_rate"] < 1.0)
    ]
    lines = [
        "# Experiment 4 运行摘要",
        "",
        "## 1. 运行状态",
        "",
        f"- Run ID: `{run_config['run_id']}`",
        f"- Run tier: `{run_config['run_tier']}`",
        f"- Result schema: `{run_config['result_schema']}`",
        f"- Engineering status: `{engineering['status']}`",
        f"- Scientific status: `{scientific['status']}`",
        f"- Paper promotion: `NOT RUN`",
        f"- Paper result: `{str(run_config['paper_result']).lower()}`",
        "",
        "## 2. 科学问题",
        "",
        "Module A 估计固定 operational route 相对 structural action comparisons 的 population raw action-gap defect。",
        "Module B 检验有限、可能选择性进入的 source-grounded audit evidence 对该 population target 的估计可靠性。",
        "Calibration controls 只评估预设 affine calibration family，不校正 structural benchmark。",
        "",
        "## 3. 冻结配置",
        "",
        f"- Module A: T={run_config['mode_settings']['module_a_decision_horizon']}, W={run_config['mode_settings']['module_a_warmup_rounds']}, seeds={len(run_config['mode_settings']['module_a_seeds'])}",
        f"- Module A grid: route-label rates={config.MODULE_A_ROUTE_LABEL_RATES}; attribution-proxy noise SDs={config.MODULE_A_ATTRIBUTION_PROXY_NOISE_SDS}",
        f"- Module B: T={run_config['mode_settings']['module_b_decision_horizon']}, W={run_config['mode_settings']['module_b_warmup_rounds']}, replications={run_config['mode_settings']['module_b_replications']}",
        f"- Audit-evidence rates={config.AUDIT_EVIDENCE_RATES}",
        "- Audit designs: MCAR unweighted; ambiguity-biased unweighted; ambiguity-biased IPW; full population at rho=1.",
        "",
        "## 4. 主要数值审计",
        "",
        f"- q_route=1 的最大 mean population defect: {q1_max:.3e}",
        f"- Ambiguity-biased unweighted raw-bias range: [{biased_rows['raw_bias'].min():.4f}, {biased_rows['raw_bias'].max():.4f}]",
        f"- Ambiguity-biased IPW raw-bias range: [{ipw_rows['raw_bias'].min():.4f}, {ipw_rows['raw_bias'].max():.4f}]",
        f"- Calibration estimable-rate range: [{proxy_audit['calibration_estimable_rate'].min():.3f}, {proxy_audit['calibration_estimable_rate'].max():.3f}]",
        "",
        "## 5. Calibration controls",
        "",
    ]
    for _, row in controls.iterrows():
        lines.append(
            f"- {row['control_display_name']}: raw={row['raw_defect_mean']:.4f}, calibrated={row['calibrated_defect_mean']:.4f}, Rec={row['estimated_recoverability_mean']:.4f}, negative-rate={row['negative_recoverability_rate']:.3f}."
        )
    lines += [
        "",
        "## 6. 解释边界",
        "",
        "- Source-labelled full-map route 是 simulator diagnostic reference；source identity 在普通日志中不自动识别 counterfactual action gaps。",
        "- IPW 使用已知 simulated inclusion probabilities；其结果不能扩展为未知选择机制下的自动识别保证。",
        "- Calibrated population target 条件于每次 replication 中拟合的 fold-specific affine maps。",
        "- Recoverability 是 calibration-family-specific discrepancy reduction，不是 route validity probability。",
        "- Fast 结果只用于接口与科学 invariant 检查，不进入正文。",
        "",
        "## 7. 主要产物",
        "",
        "- `figures/pdf/fig_exp4_route_alignment_and_audit.pdf`",
        "- `tables/tbl_exp4_audit_reliability.tex`",
        "- `derived/exp4_route_boundary_summary.csv`",
        "- `derived/exp4_audit_condition_summary.csv`",
        "- `checks/exp4_self_check.json`",
        "- `checks/exp4_scientific_check.json`",
    ]
    (run_dir / "reports" / "exp4_run_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

"""Status lineage, disclosure tables, and synchronized Exp3 run reports."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

from utilities import save_frame


READY_PREFLIGHT_STATUSES = {"READY", "READY_WITH_LIMITED_SUPPORT"}
ACCEPTED_UNCERTAINTY_STATUSES = {"SENSITIVITY_ONLY_ACCEPTED"}


def scientific_uncertainty_status(resampling: dict[str, Any]) -> str:
    role = str(resampling.get("resampling_output_role", ""))
    method = str(resampling.get("displayed_range_method", ""))
    formal = bool(resampling.get("formal_ci_validated", False))
    interface = str(resampling.get("uncertainty_interface_status", ""))
    if (
        interface == "SENSITIVITY_ONLY_ACCEPTED"
        and role == "sensitivity_only"
        and method == "percentile_user_cluster_sensitivity"
        and formal is False
    ):
        return "SENSITIVITY_ONLY_ACCEPTED"
    if not resampling:
        return "NOT_EVALUATED"
    return "FAIL"


def full_design_support_ready(preflight: dict[str, Any]) -> bool:
    explicit = preflight.get("full_design_support_ready")
    if explicit is not None:
        return bool(explicit)
    return str(preflight.get("status")) in READY_PREFLIGHT_STATUSES


def readiness_fields(manifest: dict[str, Any]) -> dict[str, object]:
    full_ready = bool(manifest.get("full_design_support_ready", False))
    recommended = all(
        (
            manifest.get("input_audit_status") == "PASS",
            manifest.get("pipeline_execution_status") == "PASS",
            manifest.get("independent_self_check_status") == "PASS",
            manifest.get("final_engineering_status") == "PASS",
            manifest.get("scientific_contract_status") == "PASS",
            manifest.get("figure_data_contract_status") == "PASS",
            full_ready,
            manifest.get("scientific_uncertainty_status") in ACCEPTED_UNCERTAINTY_STATUSES,
            manifest.get("formal_ci_validated") is False,
        )
    )
    paper_eligible = (
        str(manifest.get("run_tier")) == "full"
        and recommended
        and not bool(manifest.get("synthetic_fixture", False))
    )
    return {
        "full_design_support_ready": full_ready,
        "full_run_recommended": bool(recommended),
        "paper_promotion_eligible": bool(paper_eligible),
    }


def calculate_final_engineering_status(manifest: dict[str, Any]) -> str:
    required = (
        manifest.get("pipeline_execution_status") == "PASS",
        manifest.get("independent_self_check_status") == "PASS",
        manifest.get("figure_data_contract_status") == "PASS",
        manifest.get("artifact_manifest_status") == "PASS",
    )
    if all(required):
        return "PASS"
    if manifest.get("independent_self_check_status") == "NOT_RUN":
        return "PENDING_SELF_CHECK"
    return "FAIL"


def target_reuse_table(
    history_audit: dict[str, Any],
    evaluation_audit: dict[str, Any],
) -> pd.DataFrame:
    columns = (
        "split_id",
        "unique_user_count",
        "source_event_count",
        "eligible_source_event_count",
        "positive_outcome_event_count",
        "right_censoring_rate",
        "outcome_event_reuse_rate",
        "mean_source_windows_per_outcome_event",
        "median_source_windows_per_outcome_event",
        "p90_source_windows_per_outcome_event",
        "maximum_source_windows_per_outcome_event",
        "mean_source_events_per_user",
        "p90_source_events_per_user",
    )
    return pd.DataFrame(
        [{column: audit.get(column) for column in columns} for audit in (history_audit, evaluation_audit)]
    )


def boundary_quarantine_table(split: dict[str, Any]) -> pd.DataFrame:
    retained_nonoverlap = bool(split.get("strict_event_time_nonoverlap", False))
    common = {
        "timezone_name": split.get("timezone_name"),
        "timezone_rule": split.get("timezone_rule"),
        "boundary_policy": split.get("boundary_policy"),
        "raw_strict_event_time_nonoverlap": split.get("raw_strict_event_time_nonoverlap"),
        "raw_overlap_width_ms": split.get("raw_overlap_width_ms"),
        "retained_strict_event_time_nonoverlap": retained_nonoverlap,
    }
    return pd.DataFrame(
        [
            {
                "split_id": "history",
                "excluded_event_count": split.get("history_events_excluded_before_start", 0),
                "excluded_event_fraction": split.get("history_prestart_fraction", 0.0),
                "frozen_tolerance": split.get("max_prestart_history_fraction"),
                "tolerance_source": "run_config.max_prestart_history_fraction",
                **common,
            },
            {
                "split_id": "evaluation",
                "excluded_event_count": split.get("evaluation_events_excluded_before_boundary", 0),
                "excluded_event_fraction": split.get("evaluation_preboundary_fraction", 0.0),
                "frozen_tolerance": split.get("max_preboundary_evaluation_fraction"),
                "tolerance_source": "run_config.max_preboundary_evaluation_fraction",
                **common,
            },
        ]
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_disclosure_tables(
    output_dir: Path,
    split: dict[str, Any],
    history_audit: dict[str, Any],
    evaluation_audit: dict[str, Any],
) -> None:
    save_frame(target_reuse_table(history_audit, evaluation_audit), output_dir / "tables" / "exp3_target_reuse_audit.csv")
    save_frame(boundary_quarantine_table(split), output_dir / "tables" / "exp3_boundary_quarantine_audit.csv")


def write_run_report(output_dir: Path, manifest: dict[str, Any]) -> Path:
    split = _load_json(output_dir / "design" / "exp3_split_manifest.json")
    resampling = _load_json(output_dir / "checks" / "exp3_bootstrap_diagnostics.json")
    preflight = _load_json(output_dir / "diagnostics" / "exp3_full_design_support_preflight.json")
    history_audit = manifest.get("history_target_audit") or _load_json(
        output_dir / "diagnostics" / "exp3_history_target_audit.json"
    )
    evaluation_audit = manifest.get("evaluation_target_audit") or _load_json(
        output_dir / "diagnostics" / "exp3_evaluation_target_audit.json"
    )
    coverage_path = output_dir / "tables" / "exp3_action_space_coverage.csv"
    coverage = pd.read_csv(coverage_path) if coverage_path.exists() else pd.DataFrame()

    def exposure(scope: str) -> tuple[int, float]:
        if coverage.empty:
            return 0, float("nan")
        row = coverage[
            (coverage["split_id"] == "evaluation")
            & (coverage["design_scope"] == scope)
        ]
        if len(row) != 1:
            return 0, float("nan")
        return int(row.iloc[0]["selected_action_count"]), float(
            row.iloc[0]["selected_action_exposure_mass_coverage"]
        )

    active_action_count, active_exposure = exposure("active_run")
    full_action_count, full_exposure = exposure("full_design_preflight")
    structure_path = output_dir / "tables" / "exp3_resampling_structure_diagnostics.csv"
    structure = pd.read_csv(structure_path) if structure_path.exists() else pd.DataFrame()

    def switch_rate(route_id: str, column: str) -> float:
        if structure.empty or column not in structure.columns:
            return float("nan")
        row = structure[structure["route_id"] == route_id]
        return float(row.iloc[0][column]) if len(row) == 1 else float("nan")
    if split and history_audit and evaluation_audit:
        write_disclosure_tables(output_dir, split, history_audit, evaluation_audit)

    report = f"""# Experiment 3 Run Report

- Run ID: `{manifest.get('run_id', 'unknown')}`
- Run tier: `{manifest.get('run_tier', 'unknown')}`
- Input status: `{manifest.get('input_data_status', 'unknown')}`
- Input audit status: **{manifest.get('input_audit_status', 'NOT_EVALUATED')}**
- Input boundary status: **{manifest.get('input_boundary_status', 'NOT_EVALUATED')}**
- Pipeline execution status: **{manifest.get('pipeline_execution_status', 'NOT_EVALUATED')}**
- Independent self-check status: **{manifest.get('independent_self_check_status', 'NOT_RUN')}**
- Archival integrity check status: **{manifest.get('archival_integrity_check_status', 'NOT_RUN')}**
- Final engineering status: **{manifest.get('final_engineering_status', 'PENDING_SELF_CHECK')}**
- Scientific status: **{manifest.get('scientific_status', 'NOT_EVALUATED')}**
- Scientific contract status: **{manifest.get('scientific_contract_status', 'PENDING_SELF_CHECK')}**
- Scientific uncertainty status: **{manifest.get('scientific_uncertainty_status', 'NOT_EVALUATED')}**
- Primary result: **full-sample point estimate**
- Resampling role: **{resampling.get('resampling_output_role', 'unknown')}**
- Displayed range: **{resampling.get('displayed_range_method', 'unknown')}**
- Formal confidence interval validated: **{str(bool(resampling.get('formal_ci_validated', False))).lower()}**
- Resampling centering diagnostic: **{resampling.get('resampling_centering_status', 'unknown')}**
- Full-design support preflight: **{preflight.get('status', 'not_available')}**
- Full-design support ready: **{str(bool(manifest.get('full_design_support_ready', False))).lower()}**
- Full run recommended: **{str(bool(manifest.get('full_run_recommended', False))).lower()}**
- Paper promotion eligible: **{str(bool(manifest.get('paper_promotion_eligible', False))).lower()}**
- Paper result: **{str(bool(manifest.get('paper_result', False))).lower()}**
- Artifact manifest status: **{manifest.get('artifact_manifest_status', 'NOT_EVALUATED')}**
- Code version type: `{manifest.get('code_version_type', 'unknown')}`
- Code version: `{manifest.get('code_version', 'unknown')}`

## Uncertainty interpretation

The full-sample estimates are the primary results. The open markers and horizontal ranges summarize the empirical user-cluster resampling distribution. They are sensitivity diagnostics rather than confidence intervals and need not contain the full-sample estimate. The legacy basic-bootstrap reflection is retained only in the audit CSV.

## Selected-action exposure scope

- Primary support is complete within the selected top-{active_action_count} action space; these actions cover **{active_exposure:.1%}** of evaluation exposure mass.
- The top-{full_action_count} full-design preflight action space covers **{full_exposure:.1%}** of evaluation exposure mass.
- Action, pair, and audit-unit coverage refer to support inside the selected action space; they do not claim coverage of the entire event log.

## Boundary quarantine disclosure

- Raw split non-overlap: **{split.get('raw_strict_event_time_nonoverlap', 'unknown')}**
- Timezone rule: `{split.get('timezone_rule', 'unknown')}`
- Quarantine policy: `{split.get('boundary_policy', 'unknown')}`
- History exclusions: **{int(split.get('history_events_excluded_before_start', 0))}** ({float(split.get('history_prestart_fraction', 0.0)):.6%}); frozen tolerance {float(split.get('max_prestart_history_fraction', 0.0)):.6%}.
- Evaluation exclusions: **{int(split.get('evaluation_events_excluded_before_boundary', 0))}** ({float(split.get('evaluation_preboundary_fraction', 0.0)):.6%}); frozen tolerance {float(split.get('max_preboundary_evaluation_fraction', 0.0)):.6%}.
- Retained split strictly non-overlapping: **{split.get('strict_event_time_nonoverlap', 'unknown')}**

## Data-dependence disclosure

- History: **{int(history_audit.get('unique_user_count', 0))} users**, **{int(history_audit.get('source_event_count', 0))} source events**; outcome-event reuse rate **{float(history_audit.get('outcome_event_reuse_rate', 0.0)):.6%}**; mean/median/p90/max source windows per positive outcome event **{float(history_audit.get('mean_source_windows_per_outcome_event', 0.0)):.2f} / {float(history_audit.get('median_source_windows_per_outcome_event', 0.0)):.2f} / {float(history_audit.get('p90_source_windows_per_outcome_event', 0.0)):.2f} / {float(history_audit.get('maximum_source_windows_per_outcome_event', 0.0)):.2f}**.
- Evaluation: **{int(evaluation_audit.get('unique_user_count', 0))} users**, **{int(evaluation_audit.get('source_event_count', 0))} source events**; outcome-event reuse rate **{float(evaluation_audit.get('outcome_event_reuse_rate', 0.0)):.6%}**; mean/median/p90/max source windows per positive outcome event **{float(evaluation_audit.get('mean_source_windows_per_outcome_event', 0.0)):.2f} / {float(evaluation_audit.get('median_source_windows_per_outcome_event', 0.0)):.2f} / {float(evaluation_audit.get('p90_source_windows_per_outcome_event', 0.0)):.2f} / {float(evaluation_audit.get('maximum_source_windows_per_outcome_event', 0.0)):.2f}**.
- Source-event counts are overlapping target-window diagnostics and are not independent sample sizes.

## Resampling and route-selection structure

- Support-set switch rate: **{switch_rate('arrival_carrier', 'support_set_switch_rate_mean'):.1%}**; valid audit-unit change rate: **{switch_rate('arrival_carrier', 'valid_audit_unit_change_rate_mean'):.1%}**.
- Held-out reference-action switch rate: **{switch_rate('arrival_carrier', 'reference_action_switch_rate_mean'):.1%}**.
- Route selected-action switch rate: Arrival carrier **{switch_rate('arrival_carrier', 'route_selected_action_switch_rate_mean'):.1%}**; Historical mean **{switch_rate('history_mean_control', 'route_selected_action_switch_rate_mean'):.1%}**; Ridge proxy **{switch_rate('ridge_proxy', 'route_selected_action_switch_rate_mean'):.1%}**.
- The offset between the resampling distribution and the full-sample statistic reflects highly overlapping target windows, cell-mean changes under user resampling, held-out reference-action switching, the max-type gap statistic, and Arrival carrier selected-action switching. It is not attributed to support-set switching when that rate is zero.

Fast outputs are never paper results. Exp3 remains a logged-support recoverability diagnostic, not OPE or structural causal regret.
"""
    path = output_dir / "reports" / "EXP3_RUN_REPORT.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    return path


def synchronize_run_outputs(output_dir: Path, manifest: dict[str, Any]) -> Path:
    """Write the canonical and compatibility status/report locations together."""
    canonical = output_dir / "metadata" / "run_manifest.json"
    alias = output_dir / "manifest" / "run_manifest.json"
    for path in (canonical, alias):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    report = write_run_report(output_dir, manifest)
    shutil.copy2(report, output_dir / "EXP3_RUN_REPORT.md")
    return report

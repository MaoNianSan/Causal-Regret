from __future__ import annotations

import argparse
import json
import py_compile
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent


def _add(rows: list[dict], name: str, passed: bool, detail: str) -> None:
    print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}", flush=True)
    rows.append(
        {"check_name": name, "status": "PASS" if passed else "FAIL", "detail": detail}
    )


def static_checks(rows: list[dict]) -> None:
    python_files = [
        path for path in ROOT.rglob("*.py") if "__pycache__" not in path.parts
    ]
    failures = []
    for path in python_files:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            failures.append(f"{path.name}: {exc.msg}")
    _add(
        rows,
        "all_python_files_compile",
        not failures,
        "; ".join(failures) or f"{len(python_files)} files",
    )

    formal_files = [
        ROOT / "src" / "runner.py",
        ROOT / "run_exp2.py",
        ROOT / "stats_exp2.py",
        ROOT / "plot_exp2.py",
        ROOT / "make_tables_exp2.py",
        ROOT / "attribution_engine.py",
        ROOT / "self_check_exp2.py",
        ROOT / "src" / "common.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in formal_files)
    production_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in formal_files
        if path.name != "self_check_exp2.py"
    )
    config = (ROOT / "config_exp2.yaml").read_text(encoding="utf-8")
    runner = (ROOT / "src" / "runner.py").read_text(encoding="utf-8")
    stats = (ROOT / "stats_exp2.py").read_text(encoding="utf-8")
    plot = (ROOT / "plot_exp2.py").read_text(encoding="utf-8")
    check = (ROOT / "self_check_exp2.py").read_text(encoding="utf-8")
    finalizer = (ROOT / "finalize_exp2.py").read_text(encoding="utf-8")
    common = (ROOT / "src" / "common.py").read_text(encoding="utf-8")
    attribution = (ROOT / "attribution_engine.py").read_text(encoding="utf-8")
    construct = (ROOT / "construct_timeline.py").read_text(encoding="utf-8")
    fixture_config = (ROOT / "tests" / "fixture_config.yaml").read_text(
        encoding="utf-8"
    )
    synthetic_integration = ROOT / "tests" / "run_synthetic_integration.py"

    _add(
        rows,
        "mode_isolation",
        "shutil.rmtree" in runner and "outputs" in runner,
        "runner clears isolated outputs/<mode>",
    )
    _add(
        rows,
        "missing_input_hard_failure",
        "blocked_missing_input" in runner,
        "missing protected input exits non-zero",
    )
    _add(
        rows,
        "all_conversion_main_cohort",
        "main_cohort_id: all_conversion_candidates" in config
        and "action_unit: campaign_source_day_cell" in config,
        "all conversion candidates use source-time decision cells",
    )
    _add(
        rows,
        "source_linked_audit_only",
        "source_linked_reference" in text and "source_reference_audit_only" in check,
        "source-linked reference is restricted by semantic check",
    )
    _add(
        rows,
        "uid_bootstrap",
        "multinomial_uid_cluster_bootstrap" in config
        and "rng.integers" in stats
        and "uid_bootstrap" in stats,
        "UID-cluster percentile bootstrap implemented",
    )
    _add(
        rows,
        "main_figure_contract",
        "fig_exp2_attribution_sensitivity" in plot
        and "credit_allocation_tv_distance_vs_arrival_anchor" in plot
        and "top_k_decision_cell_overlap_vs_arrival_anchor" in plot
        and "Share of eligible source events (%)" in plot,
        "main figure displays allocation TV point-range and top-10 overlap annotations",
    )
    _add(
        rows,
        "appendix_pairwise_overlap_figure",
        "fig_app_exp2_source_route_pairwise_overlap" in plot
        and "pairwise_credit_allocation_tv_distance" in plot
        and "pairwise_top_k_overlap" in plot,
        "appendix uses pairwise TV and top-10 overlap heatmaps",
    )
    _add(
        rows,
        "appendix_diagnostics_as_tables",
        all(
            token in text
            for token in [
                "tbl_app_exp2_source_linked_audit",
                "tbl_app_exp2_candidate_window_sensitivity",
                "tbl_app_exp2_em_assignment_diagnostic",
            ]
        ),
        "source-linked, window, and EM diagnostics are tables",
    )
    _add(
        rows,
        "no_replay_as_main_endpoint",
        "sequential_replay.py" not in runner
        and "mean_daily_logged_reference_regret" not in stats,
        "deprecated temporal replay removed from formal pipeline",
    )
    _add(
        rows,
        "no_label_availability_leakage",
        "label_availability" not in stats and "label_availability" not in plot,
        "Exp2 does not reuse invalid label-mask sensitivity",
    )
    _add(
        rows,
        "honest_estimand_language",
        "source-time" in config.lower()
        and "not online policy evaluation" in config.lower()
        and "not causal regret" in config.lower(),
        "configuration preserves observational estimand boundary",
    )
    _add(
        rows,
        "source_time_cell_design",
        "campaign_source_day_cell" in config
        and "core_source_routes" in config
        and "at_least_one_core_pair_tv_above_threshold" in check,
        "source-time cells plus core-route scientific degeneracy gate",
    )
    _add(
        rows,
        "primary_metric_semantics",
        "top_k_credited_mass_per_1000_events" in stats
        and "top_k_cost_adjusted_score_per_1000_events" in stats
        and "offline_utility_per_1000" not in stats,
        "primary outcome is credited mass; cost-adjusted score is appendix-only",
    )
    _add(
        rows,
        "arrival_anchor_label",
        "Arrival-bin anchor (diagnostic)" in text
        and "diagnostic/nondeployable" in check,
        "arrival anchor is explicitly diagnostic",
    )
    _add(
        rows,
        "paper_result_finalization_gate",
        "finalize_exp2.py" in runner
        and "paper_result" in finalizer
        and "semantic self-check has failures" in finalizer,
        "full paper_result is promoted only after semantic self-check",
    )
    _add(
        rows,
        "clean_run_replot_guard",
        "not_applicable_clean_run" in check and "comparison_performed" in check,
        "clean runs do not fail the display-only hash regression guard",
    )
    _add(
        rows,
        "source_event_delay_profile_contract",
        "n_eligible_source_events" in stats
        and "source_event_share_percent" in stats
        and "conversion_event_share_percent" not in stats
        and "source_event_share_percent" in plot,
        "Panel A counts eligible source-event rows",
    )
    _add(
        rows,
        "uid_minus_one_sentinel_filter",
        "normalise_uid_identifier" in common
        and "uid_sentinel_minus_one" in construct
        and "candidate_rows_uid_sentinel_minus_one" in construct,
        "UID -1 is treated as missing and audited",
    )
    _add(
        rows,
        "stale_arrival_alias_rejected",
        "validate_exp2_config" in common
        and '"arrival_time_naive"' not in attribution
        and "arrival_bin_anchor" in config,
        "stale arrival_time_naive configuration is rejected",
    )
    _add(
        rows,
        "fixture_config_current",
        "arrival_bin_anchor" in fixture_config
        and "min_decision_cell_ambiguity_rate" in fixture_config
        and "min_core_pairwise_tv" in fixture_config
        and "min_em_positive_entropy_share" in fixture_config
        and "arrival_time_naive" not in fixture_config,
        "synthetic fixture matches production route/gate contract",
    )
    _add(
        rows,
        "synthetic_integration_runner_present",
        synthetic_integration.exists(),
        "fixture integration runner exists",
    )
    _add(
        rows,
        "input_identity_recorded",
        "input_file_identity" in runner and "raw_input_identity" in common,
        "run metadata records input size, mtime, and partial hash",
    )

    old_ids = [
        "source_labelled_update",
        "rnn_proxy_history",
        "fig_exp2_main_replay",
        "fig_exp2_delay_coupling_control",
        "fig_exp2_label_availability",
        "fig_app_exp2_source_linked_audit",
        "fig_app_exp2_top_k_sensitivity",
        "fig_app_exp2_candidate_window_sensitivity",
        "fig_app_exp2_em_assignment_diagnostic",
    ]
    found = [token for token in old_ids if token in production_text or token in config]
    _add(
        rows,
        "deprecated_ids_removed_from_formal_code",
        not found,
        "no old Exp2 route or figure ids in formal code: " + str(found),
    )
    name_violations = re.findall(r"figure_id\s*=\s*[\"']([^\"']+)[\"']", text)
    _add(
        rows,
        "figure_ids_snake_case",
        all(re.fullmatch(r"[a-z0-9_]+", item) for item in name_violations),
        "formal figure ids are snake_case: " + str(name_violations),
    )
    latex_interface = (ROOT / "docs" / "latex_interface_experiments.md").read_text(
        encoding="utf-8"
    )
    figure_ids = re.findall(r"`(fig_[a-z0-9_]+)`", latex_interface)
    required_figures = {
        "fig_exp2_attribution_sensitivity",
        "fig_app_exp2_source_route_pairwise_overlap",
    }
    _add(
        rows,
        "formal_latex_figure_interface_nonempty",
        bool(figure_ids) and required_figures.issubset(set(figure_ids)),
        "formal LaTeX figure interface contains required figure ids: "
        + str(figure_ids),
    )


def _completed_through_tables(status: dict, mode: str) -> bool:
    if status.get("status") == "success" and status.get("mode") == mode:
        return True
    if status.get("mode") != mode or status.get("failed_step") != "render_regressions":
        return False
    required_steps = {
        "precheck",
        "timeline",
        "route_assignment",
        "statistics",
        "figures",
        "tables",
    }
    observed = {
        str(step.get("step"))
        for step in status.get("steps", [])
        if int(step.get("return_code", -1)) == 0
    }
    return required_steps.issubset(observed)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Static and completed-run code check for Experiment 2."
    )
    parser.add_argument("--mode", choices=["fast", "full"], default="fast")
    parser.add_argument("--static-only", action="store_true")
    args = parser.parse_args()
    rows: list[dict] = []
    static_checks(rows)
    if not args.static_only:
        config = ROOT / ".runtime" / f"config_exp2_{args.mode}.yaml"
        if not config.exists():
            _add(
                rows,
                "completed_run_exists",
                False,
                f"missing effective config: {config}",
            )
        else:
            status_path = ROOT / "outputs" / args.mode / "metadata" / "run_status.json"
            try:
                status = json.loads(status_path.read_text(encoding="utf-8"))
            except Exception:
                status = {}
            _add(
                rows,
                "completed_run_status",
                _completed_through_tables(status, args.mode),
                json.dumps(status, ensure_ascii=False),
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "self_check.py",
                    "--mode",
                    args.mode,
                    "--config",
                    str(config),
                ],
                cwd=ROOT,
            )
            _add(
                rows,
                "self_check_passes",
                result.returncode == 0,
                f"exit_code={result.returncode}",
            )
    output = (
        ROOT
        / "outputs"
        / (args.mode if not args.static_only else "code_check")
        / "checks"
    )
    output.mkdir(parents=True, exist_ok=True)
    report = pd.DataFrame(rows)
    report.to_csv(output / "code_check_report.csv", index=False)
    (output / "code_check_report.md").write_text(
        "# Experiment 2 Code-check Report\n\n"
        + "\n".join(
            f"- [{row['status']}] {row['check_name']}: {row['detail']}" for row in rows
        ),
        encoding="utf-8",
    )
    raise SystemExit(0 if all(row["status"] == "PASS" for row in rows) else 1)


if __name__ == "__main__":
    main()

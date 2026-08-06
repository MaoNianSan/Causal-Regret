from __future__ import annotations

import importlib
import pkgutil

import exp2_core
from main import build_parser


FACADE_SYMBOLS = {
    "cohort": ["CohortBuildResult", "build_primary_cohort"],
    "data_io": [
        "PreparedRawData",
        "build_input_manifest",
        "canonical_json_hash",
        "file_sha256",
        "input_manifest_identity_hash",
        "load_config",
        "prepare_raw_log",
        "write_frame",
        "write_json",
    ],
    "routes": ["RouteBuildResult", "build_attribution_routes", "validate_credit_conservation"],
    "metrics": [
        "MetricResult",
        "PairwiseMetricState",
        "allocation_tv",
        "build_pairwise_metric_state",
        "build_route_allocations",
        "compute_ambiguity_strata_metrics",
        "compute_mean_journey_assignment_tv",
        "compute_primary_metrics",
        "compute_targeted_top_k_metrics",
        "kendall_tau_b",
        "stable_top_k",
        "top_k_overlap",
    ],
    "bootstrap": [
        "BootstrapResult",
        "attach_bootstrap_intervals",
        "build_bootstrap_bias_audit",
        "resolve_n_jobs",
        "run_uid_cluster_bootstrap",
    ],
    "targeted": ["build_robustness_summary", "run_targeted_analyses"],
    "reporting": [
        "make_ambiguity_figure",
        "make_delay_composition_figure",
        "make_main_figure",
        "make_pairwise_appendix_figure",
        "make_tables",
    ],
    "validation": ["ValidationResult", "validate_frozen_configuration", "validate_run"],
    "runner": ["run", "run_cohort_check"],
}


def test_top_level_compatibility_facades_preserve_public_symbols():
    for module_name, symbols in FACADE_SYMBOLS.items():
        module = importlib.import_module(module_name)
        for symbol in symbols:
            assert hasattr(module, symbol), f"{module_name}.{symbol} is missing"


def test_all_exp2_core_modules_import_without_cycles():
    names = sorted(
        module.name
        for module in pkgutil.walk_packages(exp2_core.__path__, prefix="exp2_core.")
    )
    for name in names:
        importlib.import_module(name)


def test_cli_command_names_and_help_contract_are_unchanged():
    parser = build_parser()
    mode_action = next(action for action in parser._actions if action.dest == "mode")
    assert tuple(mode_action.choices) == ("fast", "full", "cohort-check")
    help_text = parser.format_help()
    assert "Run Experiment 2: delayed-conversion attribution sensitivity." in help_text
    assert "--config" in help_text
    assert "--input" in help_text
    assert "--n-bootstrap" in help_text
    assert "--n-jobs" in help_text

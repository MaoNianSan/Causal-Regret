from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path


EXP2_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = EXP2_ROOT / "exp2_core"

SCIENTIFIC_FUNCTIONS = {
    "allocation_tv",
    "build_attribution_routes",
    "build_pairwise_metric_state",
    "build_primary_cohort",
    "build_route_allocations",
    "compute_ambiguity_strata_metrics",
    "compute_mean_journey_assignment_tv",
    "compute_primary_metrics",
    "compute_targeted_top_k_metrics",
    "kendall_tau_b",
    "run_targeted_analyses",
    "run_uid_cluster_bootstrap",
    "stable_top_k",
    "top_k_overlap",
    "validate_credit_conservation",
    "validate_frozen_configuration",
    "validate_run",
}


def _production_python_files() -> list[Path]:
    return sorted(CORE_ROOT.rglob("*.py"))


def test_production_implementation_files_stay_within_hard_length_limit():
    lengths = {
        path.relative_to(EXP2_ROOT).as_posix(): len(path.read_text(encoding="utf-8").splitlines())
        for path in _production_python_files()
    }
    over_limit = {path: count for path, count in lengths.items() if count > 350}
    assert not over_limit


def test_each_scientific_function_has_one_source_of_truth():
    definitions: Counter[str] = Counter()
    locations: dict[str, list[str]] = {}
    for path in _production_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in SCIENTIFIC_FUNCTIONS:
                definitions[node.name] += 1
                locations.setdefault(node.name, []).append(
                    f"{path.relative_to(EXP2_ROOT).as_posix()}:{node.lineno}"
                )
    assert definitions == Counter({name: 1 for name in SCIENTIFIC_FUNCTIONS}), locations


def test_legacy_result_terms_are_not_reintroduced_as_identifiers():
    forbidden = {
        "decision_cell_score",
        "ranking_displacement_at_k",
        "ci_lower",
        "ci_upper",
    }
    violations: list[str] = []
    for path in _production_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden:
                violations.append(f"{path.relative_to(EXP2_ROOT).as_posix()}:{node.lineno}:{node.id}")
    assert not violations

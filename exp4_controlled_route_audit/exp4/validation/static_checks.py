"""Static package checks run before any simulation stage."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from exp4.configuration.registries import ROUTE_REGISTRY
from exp4.configuration.schema import RESULT_SCHEMA


def run_static_checks(base_dir: Path) -> dict[str, Any]:
    package = base_dir / "exp4"
    python_files = list(package.rglob("*.py"))
    scientific_paths = [
        path
        for path in python_files
        if "validation" not in path.relative_to(package).parts
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in scientific_paths)
    defect_definitions = 0
    discrepancy_definitions = 0
    import_graph: dict[str, set[str]] = {}
    for path in python_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        defect_definitions += sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "compute_action_gap_defect"
            for node in ast.walk(tree)
        )
        discrepancy_definitions += sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "compute_gap_discrepancies"
            for node in ast.walk(tree)
        )
        module = ".".join(path.relative_to(base_dir).with_suffix("").parts)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
            if alias.name.startswith("exp4.")
        }
        imports.update(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("exp4.")
        )
        import_graph[module] = imports
    plotting_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (package / "reporting").glob("figures_*.py")
    )
    checks = [
        ("result_schema_v3", RESULT_SCHEMA == "exp4_controlled_route_audit_v3"),
        ("single_defect_implementation", defect_definitions == 1),
        ("single_discrepancy_implementation", discrepancy_definitions == 1),
        ("v3_pairwise_primary_present", "mean_pairwise_gap_discrepancy" in source),
        ("dormant_oracle_registry_removed", "noisy_state_oracle" not in ROUTE_REGISTRY and "latent_state_oracle" not in ROUTE_REGISTRY),
        ("module_packages_present", all((package / name).is_dir() for name in ("configuration", "simulation", "routes", "metrics", "audit", "calibration", "modules", "outputs", "reporting", "validation"))),
        ("plotting_does_not_import_scientific_engines", all(term not in plotting_source for term in ("exp4.simulation", "exp4.routes", "exp4.audit", "exp4.calibration"))),
        ("learner_logic_excluded_from_v2_package", "UCB" not in source and "learner_consequence" not in source),
        ("source_signature_semantics_present", "arrival_signature_base_noise" in source and "candidate_source_proxy" in source),
        ("middle_mode_present", '"middle"' in source),
    ]
    return {
        "check_type": "static_code_contract",
        "status": "PASS" if all(passed for _, passed in checks) else "FAIL",
        "checks": [
            {"check_name": name, "status": "PASS" if passed else "FAIL"}
            for name, passed in checks
        ],
        "active_python_files": len(python_files),
        "import_graph_nodes": len(import_graph),
    }

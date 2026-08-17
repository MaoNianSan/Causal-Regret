"""Stage dependency and config-isolation tests for Exp4 provenance."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from exp4.configuration.parameters import SHARED_DGP
from exp4.configuration.provenance import (
    aggregation_config_hash,
    reporting_config_hash,
    scientific_config_hash,
)
from exp4.configuration.registries import ROUTE_REGISTRY
from exp4.configuration.run_modes import mode_settings
from exp4.configuration.schema import (
    EXPERIMENT_DISPLAY_NAME,
    MAIN_FIGURE_ID,
    MAIN_TABLE_ID,
)
from exp4.validation.run_provenance import compute_stage_source_hashes


def _source_fixture(tmp_path: Path) -> Path:
    files = {
        "exp4/metrics/action_gaps.py": "ACTION = 1\n",
        "exp4/metrics/ranking_diagnostics.py": "RANKING = 1\n",
        "exp4/metrics/monte_carlo.py": "MONTE_CARLO = 1\n",
    }
    for relative, content in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


def test_ranking_diagnostics_and_action_gaps_are_simulation_dependencies(
    tmp_path: Path,
) -> None:
    base = _source_fixture(tmp_path)
    before = compute_stage_source_hashes(base)
    for relative in (
        "exp4/metrics/ranking_diagnostics.py",
        "exp4/metrics/action_gaps.py",
    ):
        path = base / relative
        original = path.read_text(encoding="utf-8")
        path.write_text(original + "CHANGED = True\n", encoding="utf-8")
        after = compute_stage_source_hashes(base)
        assert after["simulation_source_hash"] != before["simulation_source_hash"]
        path.write_text(original, encoding="utf-8")


def test_monte_carlo_is_aggregation_only(tmp_path: Path) -> None:
    base = _source_fixture(tmp_path)
    before = compute_stage_source_hashes(base)
    path = base / "exp4/metrics/monte_carlo.py"
    path.write_text("MONTE_CARLO = 2\n", encoding="utf-8")
    after = compute_stage_source_hashes(base)
    assert after["aggregation_source_hash"] != before["aggregation_source_hash"]
    assert after["simulation_source_hash"] == before["simulation_source_hash"]


def test_display_and_artifact_ids_do_not_change_scientific_config() -> None:
    baseline = scientific_config_hash("full")
    assert reporting_config_hash(
        experiment_display_name=EXPERIMENT_DISPLAY_NAME + " revised"
    ) != reporting_config_hash()
    assert reporting_config_hash(main_figure_id=MAIN_FIGURE_ID + "_revised") != reporting_config_hash()
    assert reporting_config_hash(main_table_id=MAIN_TABLE_ID + "_revised") != reporting_config_hash()
    assert scientific_config_hash("full") == baseline


def test_real_simulation_parameter_and_route_semantics_require_full_rerun() -> None:
    baseline = scientific_config_hash("full")
    changed_dgp = replace(SHARED_DGP, feedback_noise_sd=SHARED_DGP.feedback_noise_sd + 0.001)
    assert scientific_config_hash("full", shared_dgp=changed_dgp) != baseline

    changed_registry = {key: dict(value) for key, value in ROUTE_REGISTRY.items()}
    changed_registry["proxy_label"]["uses_future_information"] = True
    assert scientific_config_hash("full", route_registry=changed_registry) != baseline


def test_seed_counts_are_scientific_but_bootstrap_count_is_downstream_only() -> None:
    baseline_scientific = scientific_config_hash("full")
    baseline_aggregation = aggregation_config_hash("full")
    settings = mode_settings("full")

    changed_seed_count = replace(
        settings, module_a_seed_count=settings.module_a_seed_count - 1
    )
    assert scientific_config_hash("full", settings=changed_seed_count) != baseline_scientific

    changed_bootstrap = replace(
        settings, bootstrap_replications=settings.bootstrap_replications + 1
    )
    assert scientific_config_hash("full", settings=changed_bootstrap) == baseline_scientific
    assert aggregation_config_hash("full", settings=changed_bootstrap) != baseline_aggregation

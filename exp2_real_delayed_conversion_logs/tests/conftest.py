from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cohort import build_primary_cohort
from data_io import load_config, prepare_raw_log
from metrics import compute_primary_metrics
from routes import build_attribution_routes
from synthetic import create_synthetic_fixture


@pytest.fixture(scope="session")
def experiment_objects(tmp_path_factory):
    temporary = tmp_path_factory.mktemp("exp2_fixture")
    raw_path = create_synthetic_fixture(temporary / "fixture.tsv")
    config = load_config(PROJECT_ROOT / "config.yaml")
    prepared = prepare_raw_log(raw_path, config, mode="fast", progress=False)
    cohort = build_primary_cohort(prepared.candidates, prepared.impression_counts, config)
    routes = build_attribution_routes(
        cohort.eligible_candidates,
        cohort.journey_manifest,
        cohort.decision_cell_universe,
        config,
    )
    metrics = compute_primary_metrics(
        routes.assignments,
        cohort.decision_cell_universe,
        cohort.journey_manifest,
        top_k=int(config["ranking"]["primary_top_k"]),
    )
    return {
        "config": config,
        "prepared": prepared,
        "cohort": cohort,
        "routes": routes,
        "metrics": metrics,
    }

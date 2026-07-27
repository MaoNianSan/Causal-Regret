from __future__ import annotations

from pathlib import Path

import pandas as pd

from bootstrap import attach_bootstrap_intervals, run_uid_cluster_bootstrap
from data_io import build_input_manifest, input_manifest_identity_hash
from reporting import make_tables


def test_input_identity_is_location_independent(tmp_path: Path):
    left = tmp_path / "left.tsv"
    right_dir = tmp_path / "nested"
    right_dir.mkdir()
    right = right_dir / "renamed.tsv"
    payload = b"a\tb\n1\t2\n"
    left.write_bytes(payload)
    right.write_bytes(payload)

    left_manifest = build_input_manifest(left)
    right_manifest = build_input_manifest(right)
    assert left_manifest["input_location"] != right_manifest["input_location"]
    assert input_manifest_identity_hash(left_manifest) == input_manifest_identity_hash(
        right_manifest
    )


def test_synthetic_fixture_covers_all_delay_bins(experiment_objects):
    lags = experiment_objects["cohort"].eligible_candidates["source_lag_days"]
    bins = [-float("inf"), 1 / 24, 6 / 24, 1, 7, 30]
    labels = ["<=1h", "1-6h", "6-24h", "1-7d", "7-30d"]
    counts = pd.cut(lags, bins=bins, labels=labels, include_lowest=True).value_counts(
        sort=False
    )
    assert counts.gt(0).all(), counts.to_dict()


def test_manuscript_tables_use_actual_fast_bootstrap_count(experiment_objects, tmp_path: Path):
    config = experiment_objects["config"]
    cohort = experiment_objects["cohort"]
    routes = experiment_objects["routes"]
    metrics = experiment_objects["metrics"]
    bootstrap = run_uid_cluster_bootstrap(
        routes.assignments,
        cohort.journey_manifest,
        cohort.decision_cell_universe,
        config,
        mode="fast",
        metric_states=metrics.kendall_metric_states,
        n_bootstrap_override=8,
        n_jobs_override=1,
        progress=False,
    )
    arrival, pairwise = attach_bootstrap_intervals(
        metrics.arrival_displacement,
        metrics.source_route_pairwise,
        bootstrap,
    )
    make_tables(
        cohort.cohort_summary,
        arrival,
        pairwise,
        tmp_path,
        bootstrap_audit=bootstrap.audit,
    )
    cohort_table = pd.read_csv(tmp_path / "table_exp2_cohort.csv")
    repetitions = cohort_table.loc[
        cohort_table["Cohort characteristic"].eq("Bootstrap repetitions"), "Value"
    ].iloc[0]
    assert str(repetitions) == "8"

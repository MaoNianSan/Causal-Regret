from __future__ import annotations

import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix

from bootstrap import _BootstrapState, _pair_metrics, run_uid_cluster_bootstrap


def test_bootstrap_is_reproducible_across_worker_counts(experiment_objects):
    config = experiment_objects["config"]
    cohort = experiment_objects["cohort"]
    assignments = experiment_objects["routes"].assignments
    one = run_uid_cluster_bootstrap(
        assignments,
        cohort.journey_manifest,
        cohort.decision_cell_universe,
        config,
        mode="fast",
        metric_states=experiment_objects["metrics"].kendall_metric_states,
        n_bootstrap_override=8,
        n_jobs_override=1,
        progress=False,
    )
    two = run_uid_cluster_bootstrap(
        assignments,
        cohort.journey_manifest,
        cohort.decision_cell_universe,
        config,
        mode="fast",
        metric_states=experiment_objects["metrics"].kendall_metric_states,
        n_bootstrap_override=8,
        n_jobs_override=2,
        progress=False,
    )
    sort_columns = ["replication_id", "record_type", "route_left", "route_right"]
    left = one.draws.sort_values(sort_columns, kind="stable").reset_index(drop=True)
    right = two.draws.sort_values(sort_columns, kind="stable").reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right, check_exact=True)


def test_bootstrap_freezes_full_sample_support_and_audits_it(experiment_objects):
    config = experiment_objects["config"]
    cohort = experiment_objects["cohort"]
    result = run_uid_cluster_bootstrap(
        experiment_objects["routes"].assignments,
        cohort.journey_manifest,
        cohort.decision_cell_universe,
        config,
        mode="fast",
        metric_states=experiment_objects["metrics"].kendall_metric_states,
        n_bootstrap_override=12,
        n_jobs_override=1,
        progress=False,
    )
    required = {
        "full_sample_support_count",
        "bootstrap_support_count",
        "support_frozen",
        "constant_vector",
        "zero_mass_vector",
    }
    assert required.issubset(result.draws.columns)
    assert bool(result.draws["support_frozen"].all())
    assert result.draws["bootstrap_support_count"].equals(
        result.draws["full_sample_support_count"]
    )
    assert result.audit["support_frozen"] is True
    assert len(result.audit["comparisons"]) == 10
    for item in result.audit["comparisons"]:
        assert item["bootstrap_support_min"] == item["full_sample_support_count"]
        assert item["bootstrap_support_max"] == item["full_sample_support_count"]
        assert item["support_frozen"] is True
        assert "nan_fraction" in item


def test_constant_and_zero_mass_replicate_is_explicit_nan():
    support = np.ones(3, dtype=bool)
    state = _BootstrapState(
        route_matrices={},
        eligible_impressions=np.ones(3),
        tie_rank=np.arange(3),
        n_users=1,
        top_k=1,
        frozen_support_masks={("left", "right"): support},
        frozen_support_counts={("left", "right"): 3},
    )
    vectors = {
        route: {
            "credits": np.zeros(3),
            "allocation": np.zeros(3),
            "scores": np.zeros(3),
        }
        for route in ("left", "right")
    }
    result = _pair_metrics(vectors, "left", "right", state)
    assert np.isnan(result["kendall_tau_b"])
    assert result["constant_vector"] is True
    assert result["zero_mass_vector"] is True
    assert result["bootstrap_support_count"] == 3

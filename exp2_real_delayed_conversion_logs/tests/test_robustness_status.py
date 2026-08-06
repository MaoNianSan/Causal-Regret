from __future__ import annotations

from targeted import run_targeted_analyses


def test_fast_candidate_window_status_names_the_unrun_30_day_alternative(
    experiment_objects,
):
    config = experiment_objects["config"]
    targeted = run_targeted_analyses(
        prepared_candidates=experiment_objects["prepared"].candidates,
        impression_counts=experiment_objects["prepared"].impression_counts,
        primary_cohort=experiment_objects["cohort"],
        primary_metrics=experiment_objects["metrics"],
        config=config,
        mode="fast",
    )
    status = targeted.loc[
        targeted["analysis_status"].eq("NOT_RUN_IN_FAST")
        & targeted["targeted_dimension"].eq("candidate_window_days")
    ]
    assert int(config["cohort"]["primary_candidate_window_days"]) == 7
    assert [int(value) for value in config["cohort"]["robustness_candidate_window_days"]] == [30]
    assert len(status) == 1
    assert int(status.iloc[0]["targeted_value"]) == 30
    assert int(status.iloc[0]["targeted_value"]) != 7

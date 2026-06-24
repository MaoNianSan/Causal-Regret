from __future__ import annotations

from pathlib import Path
import argparse

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke-check a completed synthetic Exp2 run."
    )
    parser.add_argument("--output-root", default=str(ROOT / "outputs" / "fast"))
    args = parser.parse_args()
    output_root = Path(args.output_root)
    processed = output_root / "processed"
    summaries = output_root / "summaries"
    summary = pd.read_csv(
        processed / "exp2_conversion_uid_integrity_summary.csv"
    ).set_index("metric")["value"]
    assert float(summary["conversion_ids_missing_uid"]) >= 1
    assert float(summary["conversion_ids_cross_uid"]) >= 1
    assert (
        float(summary["candidate_rows_missing_conversion_id_before_persistence"]) >= 1
    )
    assert float(summary["candidate_rows_uid_sentinel_minus_one"]) >= 1
    assert float(summary["conversion_ids_uid_sentinel_minus_one"]) >= 1

    mapping = pd.read_csv(processed / "exp2_action_cell_mapping.csv")
    assert mapping["action_id"].nunique() > 50
    candidates = pd.read_csv(processed / "exp2_candidate_sources.csv")
    assert not candidates["uid"].astype(str).isin({"-1", "-1.0"}).any()
    delay_profile = pd.read_csv(summaries / "exp2_source_event_delay_profile.csv")
    assert {"n_eligible_source_events", "source_event_share_percent"}.issubset(
        delay_profile.columns
    )
    assert abs(float(delay_profile["source_event_share_percent"].sum()) - 100.0) < 1e-8
    assert int(delay_profile["n_eligible_source_events"].sum()) == len(candidates)
    # At least one same-campaign path must still have two source-time cells.
    multi = candidates.groupby("conversion_id")["action_id"].nunique()
    assert (multi > 1).any()
    assert candidates.groupby("conversion_id")["source_day_index"].nunique().max() > 1

    divergence = pd.read_csv(summaries / "exp2_main_route_divergence_audit.csv")
    core = {"first_click", "last_click", "linear_attribution", "time_decay_soft"}
    core_pairs = divergence[
        divergence["route_left"].isin(core) & divergence["route_right"].isin(core)
    ]
    assert (core_pairs["mean_total_variation_distance"] > 1e-12).any()

    assignments = pd.read_csv(processed / "exp2_route_assignments.csv")
    names = assignments.groupby("route")["method_display_name"].first().to_dict()
    assert names["first_click"] == "First click or touch"
    assert names["last_click"] == "Last click or touch"
    assert names["arrival_bin_anchor"] == "Arrival-bin anchor (diagnostic)"

    route = pd.read_csv(summaries / "exp2_route_sensitivity_summary.csv")
    arrival = route[route["route"].eq("arrival_bin_anchor")].iloc[0]
    assert (
        abs(float(arrival["credit_allocation_tv_distance_vs_arrival_anchor"])) < 1e-12
    )
    assert (
        abs(float(arrival["top_k_decision_cell_overlap_vs_arrival_anchor"]) - 1.0)
        < 1e-12
    )

    pairwise = pd.read_csv(summaries / "exp2_pairwise_top_k_overlap.csv")
    assert set(pairwise["top_k"]) == {10, 20, 50}
    assert pairwise["pairwise_top_k_overlap"].between(0, 1).all()
    figure_pairwise = pd.read_csv(summaries / "exp2_source_route_pairwise_overlap.csv")
    assert {
        "pairwise_credit_allocation_tv_distance",
        "pairwise_top_k_overlap",
    }.issubset(figure_pairwise.columns)
    diag = figure_pairwise[
        figure_pairwise["route_left"].eq(figure_pairwise["route_right"])
    ]
    assert (diag["pairwise_credit_allocation_tv_distance"].abs() < 1e-12).all()
    assert (diag["pairwise_top_k_overlap"].sub(1.0).abs() < 1e-12).all()

    window = pd.read_csv(processed / "exp2_candidate_window_uid_integrity.csv")
    assert (window["missing_reference"] == 0).all() and (
        window["uid_mismatch"] == 0
    ).all()
    assert (
        pd.to_numeric(window["window_bootstrap_replicates"], errors="coerce") == 0
    ).all()
    assert (
        window["window_uncertainty_status"]
        .eq("not_computed_point_estimate_common_cohort_diagnostic")
        .all()
    )
    window_table = pd.read_csv(
        output_root / "tables" / "tbl_app_exp2_candidate_window_sensitivity.csv"
    )
    assert "Common-cohort coverage" in window_table.columns

    em = pd.read_csv(summaries / "exp2_em_assignment_diagnostic.csv")
    assert float(em["nontrivial_assignment"].mean()) > 0.0

    source_audit = pd.read_csv(
        output_root / "tables" / "tbl_app_exp2_source_linked_audit.csv"
    )
    assert "attribution_nondiscriminative" in source_audit.columns
    assert "candidate_decision_cell_count_p90" in source_audit.columns
    assert source_audit["attribution_nondiscriminative"].isin([True, False]).all()

    main_data = pd.read_csv(
        output_root / "figures" / "data" / "fig_exp2_attribution_sensitivity_data.csv"
    )
    panel_b = main_data[main_data["panel_id"].eq("panel_b")]
    assert set(panel_b["method_id"]) == {
        "arrival_bin_anchor",
        "first_click",
        "last_click",
        "linear_attribution",
        "time_decay_soft",
    }
    assert set(panel_b["x_id"]) == {"credit_allocation_tv_distance_vs_arrival_anchor"}
    assert not bool(panel_b["paper_result"].any())

    metadata = pd.read_json(
        output_root
        / "figures"
        / "metadata"
        / "fig_exp2_attribution_sensitivity_metadata.json",
        typ="series",
    )
    assert metadata["metric_formula_id"]
    assert metadata["paper_result"] is False

    formal = (ROOT / "docs" / "latex_interface_experiments.md").read_text(
        encoding="utf-8"
    )
    for old_id in [
        "fig_app_exp2_source_linked_audit",
        "fig_app_exp2_top_k_sensitivity",
        "fig_app_exp2_candidate_window_sensitivity",
        "fig_app_exp2_em_assignment_diagnostic",
    ]:
        assert old_id not in formal
    print("[decision_cell_smoke] passed")


if __name__ == "__main__":
    main()

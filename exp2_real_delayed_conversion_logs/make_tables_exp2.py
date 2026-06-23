from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from attribution_engine import ROUTE_DISPLAY
from src.common import ensure_output_dirs, load_config, make_output_manifest, out_dir, save_run_metadata, write_csv


ARRIVAL_TV = "credit_allocation_tv_distance_vs_arrival_anchor"
ARRIVAL_OVERLAP = "top_k_decision_cell_overlap_vs_arrival_anchor"
ARRIVAL_MASS_DIFF = "top_k_credited_mass_difference_per_1000_events_vs_arrival_anchor"


def _read(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _write_table(frame: pd.DataFrame, root: Path, table_id: str, caption: str, label: str) -> None:
    write_csv(frame, root / f"{table_id}.csv")
    try:
        md = frame.to_markdown(index=False)
    except Exception:
        md = frame.to_csv(index=False)
    (root / f"{table_id}.md").write_text(f"# {caption}\n\n{md}\n", encoding="utf-8")
    (root / f"{table_id}.tex").write_text(
        frame.to_latex(
            index=False,
            escape=True,
            longtable=False,
            caption=caption,
            label=label,
            float_format=lambda value: f"{value:.4g}",
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Write Exp2 tables aligned with logged source-time attribution sensitivity.")
    parser.add_argument("--config", default="config_exp2.yaml")
    args = parser.parse_args()
    cfg = load_config(args.config)
    ensure_output_dirs(cfg)
    precheck = out_dir(cfg, "precheck")
    summaries = out_dir(cfg, "summaries")
    processed = out_dir(cfg, "processed")
    tables = out_dir(cfg, "tables")
    main_routes = list(map(str, cfg["reporting"]["main_figure_routes"]))

    dataset = _read(precheck / "exp2_dataset_summary.csv")
    keep = [
        "n_rows",
        "n_users_exact",
        "n_campaigns",
        "n_conversion_rows",
        "n_attributed_rows",
        "n_clicked_rows",
        "time_span_days",
        "configured_observation_window_days",
    ]
    dataset = dataset[dataset["metric"].isin(keep)].rename(columns={"metric": "Metric", "value": "Value"})
    _write_table(dataset, tables, "tbl_app_exp2_dataset_summary", "Raw-log and analysis-window summary.", "tab:app_exp2_dataset_summary")

    candidate = _read(summaries / "exp2_candidate_set_summary.csv")
    _write_table(candidate, tables, "tbl_app_exp2_candidate_set_summary", "Main and source-linked audit cohort composition.", "tab:app_exp2_candidate_set_summary")

    route_spec = _read(processed / "exp2_attribution_route_specification.csv")
    _write_table(route_spec, tables, "tbl_app_exp2_attribution_routes", "Attribution route definitions and information interfaces.", "tab:app_exp2_attribution_routes")

    main = _read(summaries / "exp2_route_sensitivity_summary.csv")
    main = main[main["route"].isin(main_routes)].copy()
    main["Route"] = main["route"].map(ROUTE_DISPLAY).fillna(main["route"])
    table = main[
        [
            "Route",
            "top_k_credited_mass_per_1000_events",
            ARRIVAL_TV,
            f"{ARRIVAL_TV}_ci_lower",
            f"{ARRIVAL_TV}_ci_upper",
            ARRIVAL_OVERLAP,
            f"{ARRIVAL_OVERLAP}_ci_lower",
            f"{ARRIVAL_OVERLAP}_ci_upper",
        ]
    ]
    table.columns = [
        "Route",
        "Top-k credited mass / 1,000",
        "Allocation TV vs arrival anchor",
        "TV CI low",
        "TV CI high",
        "Top-10 overlap vs arrival anchor",
        "Overlap CI low",
        "Overlap CI high",
    ]
    _write_table(
        table,
        tables,
        "tbl_exp2_route_sensitivity",
        "Logged route sensitivity on the all-conversion cohort. Intervals are UID-cluster bootstrap intervals for allocation and ranking summaries, not causal-policy intervals.",
        "tab:exp2_route_sensitivity",
    )

    audit = _read(summaries / "exp2_source_linked_audit.csv")
    candidate_summary = _read(summaries / "exp2_candidate_set_summary.csv")
    audit_cohort = candidate_summary[candidate_summary["cohort_id"].eq(str(cfg["subsets"]["source_linked_audit_cohort_id"]))]
    candidate_decision_cell_count_p90 = (
        float(audit_cohort["candidate_decision_cell_count_p90"].iloc[0])
        if not audit_cohort.empty
        else float("nan")
    )
    nondiscriminative = bool(
        not audit_cohort.empty and candidate_decision_cell_count_p90 <= 1.0
    )
    if nondiscriminative:
        note = (
            "This subset is bookkeeping-valid but attribution-nondiscriminative because retained conversion journeys "
            "contain at most one eligible source-time decision cell at the 90th percentile."
        )
    else:
        note = (
            "This subset is bookkeeping-valid and has candidate decision-cell p90="
            f"{candidate_decision_cell_count_p90:.4g}; route differences in this audit remain bookkeeping diagnostics, "
            "not source ground truth."
        )
    audit["Route"] = audit["route"].map(ROUTE_DISPLAY).fillna(audit["route"])
    audit["attribution_nondiscriminative"] = bool(nondiscriminative)
    audit["candidate_decision_cell_count_p90"] = candidate_decision_cell_count_p90
    audit["interpretation_note"] = note
    audit = audit[
        [
            "Route",
            "source_action_match_mass",
            "attribution_error_mass",
            "credit_allocation_tv_distance_vs_source_linked_reference",
            "top_k_decision_cell_overlap_vs_source_linked_reference",
            "candidate_decision_cell_count_p90",
            "attribution_nondiscriminative",
            "interpretation_note",
        ]
    ]
    audit.columns = [
        "Route",
        "Source-cell match mass",
        "Mismatch mass",
        "Allocation TV vs Criteo-attributed reference",
        "Top-10 overlap vs Criteo-attributed reference",
        "candidate_decision_cell_count_p90",
        "attribution_nondiscriminative",
        "interpretation_note",
    ]
    _write_table(
        audit,
        tables,
        "tbl_app_exp2_source_linked_audit",
        "Unique-labelled audit subset only. It is bookkeeping-valid but can be attribution-nondiscriminative; the Criteo-attributed reference is not complete causal ground truth.",
        "tab:app_exp2_source_linked_audit",
    )

    top_k_sensitivity = _read(summaries / "exp2_pairwise_top_k_overlap.csv")
    top_k_sensitivity["Route left"] = top_k_sensitivity["route_left"].map(ROUTE_DISPLAY).fillna(top_k_sensitivity["route_left"])
    top_k_sensitivity["Route right"] = top_k_sensitivity["route_right"].map(ROUTE_DISPLAY).fillna(top_k_sensitivity["route_right"])
    pairwise_table = top_k_sensitivity[["top_k", "Route left", "Route right", "pairwise_top_k_overlap"]]
    pairwise_table.columns = ["Top-k", "Route left", "Route right", "Pairwise overlap"]
    _write_table(
        pairwise_table,
        tables,
        "tbl_app_exp2_top_k_sensitivity",
        "Top-k source-time decision-cell overlap sensitivity. Values near the action-cell universe are not treated as robustness evidence.",
        "tab:app_exp2_top_k_sensitivity",
    )

    window = _read(summaries / "exp2_candidate_window_sensitivity.csv")
    window = window[window["route"].isin(main_routes)].copy()
    window["Route"] = window["route"].map(ROUTE_DISPLAY).fillna(window["route"])
    window = window[
        [
            "candidate_window_days",
            "window_common_cohort_events",
            "common_cohort_coverage",
            "Route",
            ARRIVAL_TV,
            ARRIVAL_OVERLAP,
            ARRIVAL_MASS_DIFF,
        ]
    ]
    window.columns = [
        "Candidate window days",
        "Common-cohort conversions",
        "Common-cohort coverage",
        "Route",
        "Allocation TV vs arrival anchor",
        "Top-10 overlap vs arrival anchor",
        "Top-k credited-mass difference / 1,000",
    ]
    _write_table(
        window,
        tables,
        "tbl_app_exp2_candidate_window_sensitivity",
        "All windows use the same conversion-ID intersection; the table separates route allocation/ranking changes from cohort coverage.",
        "tab:app_exp2_candidate_window_sensitivity",
    )

    em = _read(summaries / "exp2_em_assignment_diagnostic.csv")
    em_table = pd.DataFrame(
        {
            "Metric": [
                "Conversions evaluated",
                "Median maximum assignment mass",
                "Median assignment entropy",
                "Nontrivial entropy share",
            ],
            "Value": [
                int(len(em)),
                float(em["max_assignment_weight"].median()),
                float(em["assignment_entropy"].median()),
                float(em["nontrivial_assignment"].mean()),
            ],
        }
    )
    _write_table(
        em_table,
        tables,
        "tbl_app_exp2_em_assignment_diagnostic",
        "EM-style allocation concentration diagnostic. It is a route-validity diagnostic rather than a performance endpoint.",
        "tab:app_exp2_em_assignment_diagnostic",
    )

    cost = _read(summaries / "exp2_cost_adjusted_credit_score.csv")
    cost["Route"] = cost["route"].map(ROUTE_DISPLAY).fillna(cost["route"])
    cost = cost[
        [
            "cost_lambda",
            "Route",
            "top_k_cost_adjusted_score_per_1000_events",
            "top_k_cost_adjusted_score_difference_per_1000_events_vs_arrival_anchor",
            ARRIVAL_OVERLAP,
        ]
    ]
    cost.columns = [
        "Cost lambda",
        "Route",
        "Cost-adjusted top-k score / 1,000",
        "Cost-adjusted score difference vs arrival anchor / 1,000",
        "Top-10 overlap vs arrival anchor",
    ]
    _write_table(
        cost,
        tables,
        "tbl_app_exp2_cost_adjusted_credit_score",
        "Cost-normalization robustness check only. The transformed cost field is not interpreted as monetary profit or ROI.",
        "tab:app_exp2_cost_adjusted_credit_score",
    )

    save_run_metadata(cfg, "tables_success")
    make_output_manifest(cfg)
    print("[tables] done", flush=True)


if __name__ == "__main__":
    main()

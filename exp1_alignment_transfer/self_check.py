from __future__ import annotations

"""Engineering and scientific invariant checks for Experiment 1."""

from dataclasses import replace
import argparse
import ast
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config import DELAY, FAST_STRUCTURAL, MECHANISM_ORDER, RUN, STRUCTURAL
from main import load_frozen_calibration
from src.artifact_io import atomic_write_json, code_lineage, hash_payload, read_frame, refresh_output_manifest, sha256_file, utc_now
from src.metrics import (
    action_gap_defect,
    action_gap_defect_bruteforce,
    route_regret_increment,
    structural_regret_increment,
    transfer_slack,
)
from src.path_generator import build_shared_path_bundle
from src.route_maps import build_arrival_assigned_route_map


PROJECT_ROOT = Path(__file__).resolve().parent
STATUS_DIR = PROJECT_ROOT / "status"



def _as_list(value: Any) -> list[Any]:
    if isinstance(value, str):
        parsed = ast.literal_eval(value)
        return list(parsed)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return list(value)
    if pd.isna(value):
        return []
    return [value]


def _assert(condition: bool, name: str, details: Any = None) -> dict[str, Any]:
    if not condition:
        raise AssertionError(f"{name} failed: {details}")
    return {"check": name, "status": "PASS", "details": details}


def run_checks(run_tier: str) -> dict[str, Any]:
    output = PROJECT_ROOT / "outputs" / run_tier
    calibration = load_frozen_calibration()
    path_manifest = read_frame(output / "raw" / "exp1_path_manifest.parquet")
    route_round = read_frame(output / "raw" / "exp1_route_diagnostic_rounds.parquet")
    learner_round = read_frame(output / "raw" / "exp1_learner_consequence_rounds.parquet")
    route_seed = read_frame(output / "seed_metrics" / "exp1_route_seed_metrics.parquet")
    learner_seed = read_frame(output / "seed_metrics" / "exp1_learner_seed_metrics.parquet")

    checks: list[dict[str, Any]] = []
    checks.append(_assert(not path_manifest.empty, "path_manifest_nonempty", len(path_manifest)))
    checks.append(_assert(not route_round.empty, "route_round_nonempty", len(route_round)))
    checks.append(_assert(not learner_round.empty, "learner_round_nonempty", len(learner_round)))

    expected_seeds = tuple(RUN.fast_seeds if run_tier == "fast" else RUN.evaluation_seeds)
    observed_seeds = tuple(sorted(path_manifest.seed.astype(int).unique()))
    checks.append(_assert(observed_seeds == expected_seeds, "exact_seed_set", {"expected": expected_seeds, "observed": observed_seeds}))
    observed_mechanisms = tuple(path_manifest.mechanism_id.drop_duplicates())
    checks.append(_assert(observed_mechanisms == tuple(MECHANISM_ORDER), "exact_mechanism_order", observed_mechanisms))
    expected_bundles = len(expected_seeds) * len(MECHANISM_ORDER)
    checks.append(_assert(len(path_manifest) == expected_bundles, "complete_seed_mechanism_matrix", expected_bundles))
    horizon = 500 if run_tier == "fast" else 5000
    checks.append(_assert(len(route_round) == expected_bundles * 2 * horizon, "exact_route_round_count", len(route_round)))
    checks.append(_assert(len(learner_round) == expected_bundles * 2 * horizon, "exact_learner_round_count", len(learner_round)))
    checks.append(_assert(set(route_round.route_id.unique()) == {"arrival_assigned", "source_bound"}, "exact_route_set"))
    checks.append(_assert(set(learner_round.feedback_binding_id.unique()) == {"arrival_clock", "source_round"}, "exact_binding_set"))

    checks.append(
        _assert(
            float(path_manifest.structural_loss_min.min()) >= -1e-12
            and float(path_manifest.structural_loss_max.max()) <= 1.0 + 1e-12,
            "full_structural_loss_bounds",
            [float(path_manifest.structural_loss_min.min()), float(path_manifest.structural_loss_max.max())],
        )
    )
    checks.append(_assert(int(path_manifest.loss_clipping_count.sum()) == 0, "no_loss_clipping", int(path_manifest.loss_clipping_count.sum())))
    checks.append(_assert(set(path_manifest.learner_prehistory_policy.unique()) == {"cold_start_empty_queue"}, "learner_prehistory_policy_frozen"))

    zero_arrival = route_round[
        (route_round.mechanism_id == "zero_delay")
        & (route_round.route_id == "arrival_assigned")
    ]
    checks.append(
        _assert(
            float(zero_arrival.delta_gap.abs().max()) <= 1e-10,
            "zero_delay_arrival_map_identity",
            float(zero_arrival.delta_gap.abs().max()),
        )
    )
    exact_arrival = route_seed[
        (route_seed.mechanism_id == "exact_valid_shift")
        & (route_seed.route_id == "arrival_assigned")
    ]
    checks.append(
        _assert(
            float(exact_arrival.alignment_budget_rate.abs().max()) <= 1e-10,
            "exact_valid_alignment_budget_zero",
            float(exact_arrival.alignment_budget_rate.abs().max()),
        )
    )
    source_rows = route_round[route_round.route_id == "source_bound"]
    checks.append(
        _assert(
            float(source_rows.delta_gap.abs().max()) <= 1e-10,
            "source_bound_map_identity",
            float(source_rows.delta_gap.abs().max()),
        )
    )
    arrival_route = route_round[route_round.route_id == "arrival_assigned"]
    weight_errors = []
    future_use = 0
    update_mismatch = 0
    for row in arrival_route.itertuples(index=False):
        sources = _as_list(row.source_rounds)
        weights = [float(x) for x in _as_list(row.source_weights)]
        if sources:
            weight_errors.append(abs(sum(weights) - 1.0))
            if len(set(round(float(w), 12) for w in weights)) != 1:
                weight_errors.append(1.0)
            future_use += sum(int(source > row.t) for source in sources)
        update_mismatch += int(bool(row.route_map_updated) != bool(row.arrival_batch_size > 0))
    checks.append(_assert(max(weight_errors or [0.0]) <= 1e-12, "uniform_arrival_batch_weights", max(weight_errors or [0.0])))
    checks.append(_assert(future_use == 0, "empty_clock_and_route_map_no_future_use", future_use))
    checks.append(_assert(update_mismatch == 0, "route_map_updated_audit", update_mismatch))

    checks.append(
        _assert(
            bool(route_seed.transfer_invariant_pass.all()),
            "transfer_invariant_all_seed_route_mechanism",
            int((~route_seed.transfer_invariant_pass).sum()),
        )
    )

    # Exact-valid and geometric mechanisms must share the same delay realization per seed.
    delay_pivot = path_manifest[
        path_manifest.mechanism_id.isin(["exact_valid_shift", "geometric_delay"])
    ].pivot(index="seed", columns="mechanism_id", values="delay_path_hash")
    checks.append(
        _assert(
            bool((delay_pivot.exact_valid_shift == delay_pivot.geometric_delay).all()),
            "exact_valid_geometric_shared_delay_path",
            int((delay_pivot.exact_valid_shift != delay_pivot.geometric_delay).sum()),
        )
    )

    zero_learner = learner_round[learner_round.mechanism_id == "zero_delay"]
    arrival = zero_learner[zero_learner.feedback_binding_id == "arrival_clock"]
    source = zero_learner[zero_learner.feedback_binding_id == "source_round"]
    merged = arrival.merge(source, on=["seed", "t"], suffixes=("_arrival", "_source"))
    checks.append(
        _assert(
            bool((merged.action_arrival == merged.action_source).all()),
            "zero_delay_learner_actions_identical",
            int((merged.action_arrival != merged.action_source).sum()),
        )
    )
    checks.append(
        _assert(
            bool(np.allclose(merged.selected_probability_arrival, merged.selected_probability_source)),
            "zero_delay_learner_probabilities_identical",
            float(np.max(np.abs(merged.selected_probability_arrival - merged.selected_probability_source))),
        )
    )
    checks.append(
        _assert(
            bool((merged.log_weight_hash_arrival == merged.log_weight_hash_source).all()),
            "zero_delay_learner_states_identical",
            int((merged.log_weight_hash_arrival != merged.log_weight_hash_source).sum()),
        )
    )
    checks.append(
        _assert(
            bool((learner_round.read_full_loss_vector == False).all()),  # noqa: E712
            "learner_full_map_isolation",
            int((learner_round.read_full_loss_vector != False).sum()),  # noqa: E712
        )
    )
    checks.append(
        _assert(
            float(learner_round.factual_loss.min()) >= -1e-12
            and float(learner_round.factual_loss.max()) <= 1.0 + 1e-12,
            "learner_factual_loss_unit_interval",
            [float(learner_round.factual_loss.min()), float(learner_round.factual_loss.max())],
        )
    )

    source_updates = learner_round[learner_round.feedback_binding_id == "source_round"]
    arrival_updates = learner_round[learner_round.feedback_binding_id == "arrival_clock"]
    source_mismatch = 0
    for row in source_updates.itertuples(index=False):
        source_mismatch += int(_as_list(row.updated_action_indices) != _as_list(row.arrived_source_actions))
        source_mismatch += int(not np.allclose([float(x) for x in _as_list(row.update_probabilities)], [float(x) for x in _as_list(row.arrived_source_probabilities)], atol=0.0, rtol=0.0))
    arrival_mismatch = 0
    for row in arrival_updates.itertuples(index=False):
        arrival_mismatch += int(any(int(a) != int(row.action) for a in _as_list(row.updated_action_indices)))
        arrival_mismatch += int(any(int(c) != int(row.context_cell) for c in _as_list(row.updated_context_cells)))
        arrival_mismatch += int(not np.allclose([float(p) for p in _as_list(row.update_probabilities)], float(row.selected_probability), atol=1e-15, rtol=1e-12))
    checks.append(_assert(source_mismatch == 0, "source_round_uses_source_action_and_probability", source_mismatch))
    checks.append(_assert(arrival_mismatch == 0, "arrival_clock_uses_preaction_current_binding", arrival_mismatch))
    tape_uniforms = learner_round.groupby(["seed", "mechanism_id", "t"])["shared_action_uniform"].nunique().max()
    checks.append(_assert(int(tape_uniforms) == 1, "shared_action_uniform_across_bindings", int(tape_uniforms)))

    # Raw-to-seed reconstruction.
    reconstructed_route = (
        route_round.groupby(["seed", "mechanism_id", "route_id"], as_index=False)
        .agg(
            structural_regret=("structural_regret_increment", "sum"),
            route_regret=("route_regret_increment", "sum"),
            alignment_budget=("delta_gap", "sum"),
        )
    )
    compared = reconstructed_route.merge(
        route_seed[
            ["seed", "mechanism_id", "route_id", "structural_regret", "route_regret", "alignment_budget"]
        ],
        on=["seed", "mechanism_id", "route_id"],
        suffixes=("_raw", "_seed"),
    )
    reconstruction_error = max(
        float(np.max(np.abs(compared[f"{metric}_raw"] - compared[f"{metric}_seed"])))
        for metric in ("structural_regret", "route_regret", "alignment_budget")
    )
    checks.append(
        _assert(reconstruction_error <= 1e-9, "route_raw_to_seed_reconstruction", reconstruction_error)
    )

    reconstructed_learner = (
        learner_round.groupby(["seed", "mechanism_id", "feedback_binding_id"], as_index=False)
        .agg(structural_regret=("structural_regret_increment", "sum"))
    )
    compared_learner = reconstructed_learner.merge(
        learner_seed[
            ["seed", "mechanism_id", "feedback_binding_id", "structural_regret"]
        ],
        on=["seed", "mechanism_id", "feedback_binding_id"],
        suffixes=("_raw", "_seed"),
    )
    learner_reconstruction_error = float(
        np.max(np.abs(compared_learner.structural_regret_raw - compared_learner.structural_regret_seed))
    )
    checks.append(
        _assert(
            learner_reconstruction_error <= 1e-9,
            "learner_raw_to_seed_reconstruction",
            learner_reconstruction_error,
        )
    )

    # Independent formula checks from rebuilt bundles.
    selected = calibration["structural"]["selected_value"]
    base = FAST_STRUCTURAL if run_tier == "fast" else STRUCTURAL
    structural_config = replace(
        base,
        ar_coefficient=float(selected["ar_coefficient"]),
        innovation_sd=float(selected["innovation_sd"]),
    )
    sample_seed = int(path_manifest.seed.iloc[0])
    formula_details = []
    for mechanism in path_manifest.mechanism_id.unique():
        bundle = build_shared_path_bundle(
            sample_seed, mechanism, calibration, structural_config, DELAY
        )
        route = build_arrival_assigned_route_map(bundle)
        structural_loss = bundle.structural_path.structural_loss_matrix[
            bundle.structural_path.source_rounds >= 0
        ]
        rng = np.random.default_rng(991_001)
        sample = np.sort(rng.choice(structural_loss.shape[0], size=min(25, structural_loss.shape[0]), replace=False))
        fast_delta = action_gap_defect(route.route_loss_matrix[sample], structural_loss[sample])
        brute_delta = action_gap_defect_bruteforce(route.route_loss_matrix[sample], structural_loss[sample])
        delta_error = float(np.max(np.abs(fast_delta - brute_delta)))
        actions = rng.integers(0, structural_loss.shape[1], size=structural_loss.shape[0])
        sr = float(np.sum(structural_regret_increment(actions, structural_loss)))
        rr = float(np.sum(route_regret_increment(actions, route.route_loss_matrix)))
        budget = float(np.sum(action_gap_defect(route.route_loss_matrix, structural_loss)))
        slack, tolerance = transfer_slack(sr, rr, budget, structural_loss.shape[0])
        formula_details.append(
            {"mechanism_id": mechanism, "delta_formula_error": delta_error, "random_action_slack": slack}
        )
        if delta_error > 1e-12 or slack < -tolerance:
            raise AssertionError(f"independent formula check failed: {formula_details[-1]}")
    checks.append(_assert(True, "independent_delta_and_transfer_formula_checks", formula_details))

    checks.append(
        _assert(
            not bool(path_manifest.paper_result.any()),
            "nonpromoted_run_not_paper_eligible",
            path_manifest.paper_result.unique().tolist(),
        )
    )
    checks.append(
        _assert(
            not any(
                payload.get("evaluation_seed_overlap", False)
                for payload in (
                    calibration["structural"],
                    calibration["delay"],
                    calibration["misbinding"],
                    calibration["context"],
                )
            ),
            "calibration_evaluation_seed_separation",
        )
    )


    # Derived-to-figure/table reconstruction and manuscript gating.
    route_summary = pd.read_csv(output / "derived" / "exp1_route_summary.csv")
    learner_summary = pd.read_csv(output / "derived" / "exp1_learner_summary.csv")
    contrasts = pd.read_csv(output / "derived" / "exp1_actual_learner_contrasts.csv")
    figure_data = pd.read_csv(output / "figures" / "data" / "fig_exp1_alignment_transfer_data.csv")
    mechanism_table = pd.read_csv(output / "tables" / "tab_exp1_mechanism_summary.csv")
    reconstruction_errors: list[float] = []
    for mechanism in MECHANISM_ORDER:
        for panel, series, metric in (
            ("A", "alignment_budget_rate", "alignment_budget_rate"),
            ("A", "generated_mean_delay", "generated_mean_delay"),
            ("A", "ranking_reversal_rate", "ranking_reversal_rate"),
            ("B", "structural_regret_rate", "structural_regret_rate"),
            ("B", "transfer_bound_rate", "transfer_bound_rate"),
        ):
            plotted = figure_data[(figure_data.mechanism_id == mechanism) & (figure_data.panel_id == panel) & (figure_data.series_id == series)].iloc[0]
            source_value = route_summary[(route_summary.mechanism_id == mechanism) & (route_summary.route_id == "arrival_assigned") & (route_summary.metric_id == metric)].iloc[0]
            reconstruction_errors.extend(abs(float(plotted[field]) - float(source_value[field])) for field in ("estimate", "ci_lower", "ci_upper"))
        for binding in ("arrival_clock", "source_round"):
            plotted = figure_data[(figure_data.mechanism_id == mechanism) & (figure_data.panel_id == "C") & (figure_data.series_id == binding)].iloc[0]
            source_value = learner_summary[(learner_summary.mechanism_id == mechanism) & (learner_summary.feedback_binding_id == binding) & (learner_summary.metric_id == "structural_regret_rate")].iloc[0]
            reconstruction_errors.extend(abs(float(plotted[field]) - float(source_value[field])) for field in ("estimate", "ci_lower", "ci_upper"))
        plotted = figure_data[(figure_data.mechanism_id == mechanism) & (figure_data.panel_id == "C") & (figure_data.series_id == "paired_contrast")].iloc[0]
        source_value = contrasts[contrasts.mechanism_id == mechanism].iloc[0]
        reconstruction_errors.extend(abs(float(plotted[field]) - float(source_value[field])) for field in ("estimate", "ci_lower", "ci_upper"))
    checks.append(_assert(max(reconstruction_errors or [0.0]) <= 1e-12, "summary_to_figure_data_reconstruction", max(reconstruction_errors or [0.0])))

    table_errors: list[float] = []
    for row in mechanism_table.itertuples(index=False):
        for metric, column in (("generated_mean_delay", "mean_delay"), ("alignment_budget_rate", "alignment_budget_rate"), ("ranking_reversal_rate", "ranking_reversal_rate"), ("margin_preservation_rate", "margin_preservation_rate")):
            source_value = route_summary[(route_summary.mechanism_id == row.mechanism_id) & (route_summary.route_id == "arrival_assigned") & (route_summary.metric_id == metric)].iloc[0]
            table_errors.extend(abs(float(getattr(row, column + suffix)) - float(source_value[field])) for suffix, field in (("", "estimate"), ("_ci_lower", "ci_lower"), ("_ci_upper", "ci_upper")))
        contrast = contrasts[contrasts.mechanism_id == row.mechanism_id].iloc[0]
        table_errors.extend(abs(float(getattr(row, column)) - float(contrast[field])) for column, field in (("arrival_minus_source_regret_rate", "estimate"), ("arrival_minus_source_ci_lower", "ci_lower"), ("arrival_minus_source_ci_upper", "ci_upper")))
    checks.append(_assert(max(table_errors or [0.0]) <= 1e-12, "summary_to_table_reconstruction", max(table_errors or [0.0])))

    figure_metadata_path = output / "figures" / "data" / "fig_exp1_alignment_transfer_metadata.json"
    figure_metadata = json.loads(figure_metadata_path.read_text(encoding="utf-8"))
    checks.append(_assert(figure_metadata.get("source_data_sha256") == sha256_file(output / "figures" / "data" / "fig_exp1_alignment_transfer_data.csv"), "figure_data_sha256_matches_metadata"))
    latex_text = (output / "tables" / "tab_exp1_mechanism_summary.tex").read_text(encoding="utf-8")
    checks.append(_assert("[" in latex_text and "]" in latex_text, "latex_table_contains_intervals"))
    macro_text = (output / "manuscript" / "exp1_manuscript_macros.tex").read_text(encoding="utf-8")
    values_payload = json.loads((output / "manuscript" / "exp1_manuscript_values.json").read_text(encoding="utf-8"))
    checks.append(_assert("LearnerContrast" not in macro_text and "Alignment}{" not in macro_text, "nonpromoted_numerical_macros_withheld"))
    checks.append(_assert(values_payload.get("manuscript_values_available") is False and values_payload.get("mechanisms") == {}, "nonpromoted_manuscript_values_withheld"))

    expected_calibration_hash = hash_payload(calibration["manifest"])
    for frame_name, frame in (("path", path_manifest), ("route", route_round), ("learner", learner_round)):
        checks.append(_assert(frame.calibration_manifest_hash.nunique() == 1 and frame.calibration_manifest_hash.iloc[0] == expected_calibration_hash, f"{frame_name}_calibration_lineage"))
        checks.append(_assert(frame.generated_at.notna().all(), f"{frame_name}_generated_at_complete"))

    refresh_output_manifest(output)
    manifest_payload = json.loads((output / "metadata" / "artifact_manifest.json").read_text(encoding="utf-8"))
    absolute_paths = [record["path"] for record in manifest_payload.get("artifacts", []) if Path(record["path"]).is_absolute()]
    checks.append(_assert(not absolute_paths, "artifact_manifest_uses_relative_paths", absolute_paths[:3]))

    manifest_hashes = calibration["manifest"].get("artifact_hashes", {})
    actual_hashes = {key: hash_payload(calibration[key]) for key in ("structural", "delay", "misbinding", "context")}
    checks.append(_assert(manifest_hashes == actual_hashes, "calibration_artifact_hashes_match", actual_hashes))
    memo_texts = [path.read_text(encoding="utf-8").lower() for path in PROJECT_ROOT.glob("CHANGE_MEMO_EXP1_*.md")]
    unapproved = [text for text in memo_texts if "approved_status: approved" not in text]
    checks.append(_assert(not unapproved, "all_change_memos_approved", len(unapproved)))
    report = {
        "experiment_id": "exp1_alignment_transfer",
        "run_tier": run_tier,
        "engineering_status": "PASS",
        "scientific_status": "PASS",
        "paper_promotion_status": "ELIGIBLE_FOR_PROMOTION_REVIEW" if run_tier == "full" else "FAST_NOT_PAPER_ELIGIBLE",
        "paper_result": False,
        "checks": checks,
        "generated_at": utc_now(),
    }
    report_path = output / "checks" / "exp1_validation_report.json"
    atomic_write_json(report_path, report)
    run_state_path = output / "metadata" / "run_state.json"
    state = json.loads(run_state_path.read_text(encoding="utf-8"))
    state.update(
        {
            "status": f"{run_tier.upper()}_VALIDATED",
            "engineering_status": "PASS",
            "scientific_status": "PASS",
            "paper_result": False,
            "validation_report": "checks/exp1_validation_report.json",
            "validated_at": utc_now(),
        }
    )
    atomic_write_json(run_state_path, state)
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        STATUS_DIR / f"{run_tier}_validation_status.json",
        {
            "stage": f"{run_tier}_validation",
            "status": "PASS",
            "engineering_status": "PASS",
            "scientific_status": "PASS",
            "paper_result": False,
            "paper_promotion_status": report["paper_promotion_status"],
            "report": f"outputs/{run_tier}/checks/exp1_validation_report.json",
            "code_commit": calibration["manifest"].get("code_commit"),
            "code_lineage": code_lineage(PROJECT_ROOT),
            "calibration_manifest_hash": hash_payload(calibration["manifest"]),
            "generated_at": utc_now(),
        },
    )
    refresh_output_manifest(output)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_tier", nargs="?", choices=("fast", "full"))
    parser.add_argument("--run", dest="run_option", choices=("fast", "full"))
    args = parser.parse_args()
    run_tier = args.run_option or args.run_tier
    if run_tier is None:
        parser.error("provide run tier positionally or with --run")
    report = run_checks(run_tier)
    print("SELF_CHECK_COMPLETE")
    print(f"engineering_status={report['engineering_status']}")
    print(f"scientific_status={report['scientific_status']}")
    print(f"paper_promotion_status={report['paper_promotion_status']}")
    print(f"report={PROJECT_ROOT / 'outputs' / run_tier / 'checks' / 'exp1_validation_report.json'}")


if __name__ == "__main__":
    main()

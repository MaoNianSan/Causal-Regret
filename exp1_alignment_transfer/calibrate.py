from __future__ import annotations

"""Freeze all design-calibration artifacts before evaluation runs."""

from dataclasses import asdict, replace
import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr

from config import DELAY, RUN, STRUCTURAL, config_hash
from src.artifact_io import atomic_write_json, code_lineage, git_commit, hash_payload, utc_now
from src.contracts import CalibrationError, EXPERIMENT_ID
from src.delay_mechanisms import (
    generate_fixed_delay,
    generate_geometric_delay,
    generate_mixture_delay,
    generate_state_coupled_delay,
    solve_geometric_probability,
    solve_mixture_weight,
    solve_state_coupled_intercept,
)
from src.metrics import ranking_reversal, reversal_margin
from src.path_generator import SharedPathBundle
from src.route_maps import build_arrival_assigned_route_map
from src.structural_process import (
    generate_smooth_bounded_ar1_path,
    generate_systematic_misbinding_path,
)


PROJECT_ROOT = Path(__file__).resolve().parent
CALIBRATION_DIR = PROJECT_ROOT / "calibration"
STATUS_DIR = PROJECT_ROOT / "status"


def _structural_candidate_metrics(paths) -> dict[str, float]:
    best_parts = []
    margin_parts = []
    switches = 0
    switch_denominator = 0
    state_pairs = []
    run_lengths = []
    for path in paths:
        eval_mask = path.source_rounds >= 0
        best = np.argmin(path.structural_loss_matrix[eval_mask], axis=1)
        best_parts.append(best)
        margin_parts.append(path.structural_margin[eval_mask])
        switches += int(np.sum(best[1:] != best[:-1]))
        switch_denominator += max(0, best.size - 1)
        states = path.structural_state[eval_mask]
        if states.size > 1:
            state_pairs.append((states[:-1], states[1:]))
        if best.size:
            changes = np.flatnonzero(np.r_[True, best[1:] != best[:-1], True])
            run_lengths.extend(np.diff(changes).astype(int).tolist())
    best_all = np.concatenate(best_parts)
    margins = np.concatenate(margin_parts)
    counts = np.bincount(best_all, minlength=paths[0].action_locations.size).astype(float)
    probabilities = counts / counts.sum()
    positive = probabilities[probabilities > 0]
    entropy = float(-np.sum(positive * np.log(positive)) / np.log(probabilities.size))
    spacing = 2.0 / (probabilities.size - 1)
    near_threshold = 0.1 * (spacing / 2.0) ** 2
    if state_pairs:
        left = np.concatenate([pair[0] for pair in state_pairs])
        right = np.concatenate([pair[1] for pair in state_pairs])
        state_autocorrelation = float(np.corrcoef(left, right)[0, 1])
    else:
        state_autocorrelation = float("nan")
    return {
        "normalized_optimal_action_entropy": entropy,
        "max_optimal_action_share": float(np.max(probabilities)),
        "optimal_action_switch_rate": float(switches / max(1, switch_denominator)),
        "lag1_structural_state_autocorrelation": state_autocorrelation,
        "median_optimal_action_run_length": float(np.median(run_lengths)) if run_lengths else 0.0,
        "near_tie_share": float(np.mean(margins < near_threshold)),
        "near_tie_threshold": float(near_threshold),
    }


def calibrate_structural() -> tuple[dict[str, Any], list]:
    candidates = [(0.95, 0.15), (0.95, 0.25), (0.98, 0.15), (0.98, 0.25)]
    records = []
    paths_by_candidate = {}
    for rho, sigma in candidates:
        cfg = replace(STRUCTURAL, ar_coefficient=rho, innovation_sd=sigma)
        paths = [generate_smooth_bounded_ar1_path(cfg, seed) for seed in RUN.calibration_seeds]
        metrics = _structural_candidate_metrics(paths)
        passed = bool(
            metrics["normalized_optimal_action_entropy"] >= 0.70
            and metrics["max_optimal_action_share"] <= 0.40
            and 0.80 <= metrics["lag1_structural_state_autocorrelation"] <= 0.995
            and metrics["median_optimal_action_run_length"] >= 2.0
            and metrics["near_tie_share"] <= 0.15
        )
        record = {
            "ar_coefficient": rho,
            "innovation_sd": sigma,
            "metrics": metrics,
            "passes_gates": passed,
        }
        records.append(record)
        paths_by_candidate[(rho, sigma)] = paths

    passing = [record for record in records if record["passes_gates"]]
    if not passing:
        raise CalibrationError(f"No structural candidate passed frozen gates: {records}")
    preferred = next(
        (
            record
            for record in passing
            if record["ar_coefficient"] == 0.98 and record["innovation_sd"] == 0.25
        ),
        None,
    )
    if preferred is None:
        passing.sort(
            key=lambda record: (
                record["metrics"]["normalized_optimal_action_entropy"],
                record["ar_coefficient"],
            ),
            reverse=True,
        )
        preferred = passing[0]
    selected_key = (preferred["ar_coefficient"], preferred["innovation_sd"])
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "artifact_id": "exp1_structural_calibration",
        "candidate_set": [
            {"ar_coefficient": rho, "innovation_sd": sigma} for rho, sigma in candidates
        ],
        "selection_criterion": (
            "pass nondegeneracy gates based on action support, state persistence, run length, "
            "and near ties; retain (0.98,0.25) if it passes, otherwise maximize normalized "
            "optimal-action entropy with larger rho as tie-break"
        ),
        "calibration_seed_ids": list(RUN.calibration_seeds),
        "selected_value": {
            "ar_coefficient": preferred["ar_coefficient"],
            "innovation_sd": preferred["innovation_sd"],
        },
        "calibration_metrics": records,
        "evaluation_seed_overlap": bool(
            set(RUN.calibration_seeds).intersection(RUN.evaluation_seeds)
        ),
        "generated_at": utc_now(),
    }
    return artifact, paths_by_candidate[selected_key]


def calibrate_context(paths) -> dict[str, Any]:
    contexts = np.concatenate([path.public_context[path.source_rounds >= 0] for path in paths])
    losses = np.concatenate([path.structural_loss_matrix[path.source_rounds >= 0] for path in paths])
    quantiles = np.arange(1, STRUCTURAL.k_actions, dtype=float) / STRUCTURAL.k_actions
    boundaries = np.quantile(contexts, quantiles)
    if np.any(np.diff(boundaries) <= 0):
        raise CalibrationError("Context quantile boundaries are not strictly increasing")
    cells = np.searchsorted(boundaries, contexts, side="right")
    oracle_actions = []
    cell_counts = []
    cell_mean_losses = []
    for cell in range(STRUCTURAL.k_actions):
        mask = cells == cell
        if not np.any(mask):
            raise CalibrationError(f"Context calibration cell {cell} is empty")
        means = np.mean(losses[mask], axis=0)
        oracle_actions.append(int(np.argmin(means)))
        cell_counts.append(int(np.sum(mask)))
        cell_mean_losses.append(means.tolist())
    return {
        "experiment_id": EXPERIMENT_ID,
        "artifact_id": "exp1_context_partition",
        "candidate_set": {"n_context_cells": STRUCTURAL.k_actions, "method": "equal_probability"},
        "selection_criterion": "frozen equal-probability calibration quantiles",
        "calibration_seed_ids": list(RUN.calibration_seeds),
        "boundaries": boundaries.tolist(),
        "cell_oracle_actions": oracle_actions,
        "cell_counts": cell_counts,
        "cell_mean_structural_losses": cell_mean_losses,
        "evaluation_seed_overlap": bool(
            set(RUN.calibration_seeds).intersection(RUN.evaluation_seeds)
        ),
        "generated_at": utc_now(),
    }


def calibrate_delay(paths) -> dict[str, Any]:
    p_geom = solve_geometric_probability(DELAY.target_mean_delay, DELAY.d_max)
    w_mix = solve_mixture_weight(DELAY.target_mean_delay, DELAY.d_max)
    intercept = solve_state_coupled_intercept(
        paths,
        beta=DELAY.state_coupling_beta,
        d_max=DELAY.d_max,
        target_mean=DELAY.target_mean_delay,
    )
    geometric = [generate_geometric_delay(path, p_geom, DELAY.d_max) for path in paths]
    mixture = [generate_mixture_delay(path, w_mix, DELAY.d_max) for path in paths]
    coupled = [
        generate_state_coupled_delay(
            path, intercept, DELAY.state_coupling_beta, DELAY.d_max
        )
        for path in paths
    ]
    pooled = {
        "geometric_delay": np.concatenate([path.delays for path in geometric]),
        "mixture_delay": np.concatenate([path.delays for path in mixture]),
        "state_coupled_delay": np.concatenate([path.delays for path in coupled]),
    }
    pooled_states = np.concatenate([path.structural_state for path in paths])
    means = {key: float(np.mean(value)) for key, value in pooled.items()}
    q90 = {key: float(np.quantile(value, 0.90)) for key, value in pooled.items()}
    coupling = float(spearmanr(pooled["state_coupled_delay"], pooled_states).statistic)
    mean_gate = all(abs(value - DELAY.target_mean_delay) <= 0.25 for value in means.values())
    pair_gate = max(means.values()) - min(means.values()) <= 0.25
    tail_gate = q90["mixture_delay"] >= 1.20 * q90["geometric_delay"]
    coupling_gate = abs(coupling) >= 0.20
    if not all([mean_gate, pair_gate, tail_gate, coupling_gate]):
        raise CalibrationError(
            "Delay calibration failed frozen mechanism gates: "
            f"means={means}, q90={q90}, coupling={coupling}"
        )
    return {
        "experiment_id": EXPERIMENT_ID,
        "artifact_id": "exp1_delay_calibration",
        "candidate_set": {
            "geometric_probability": "binary search over truncated geometric mean",
            "mixture_components": {"p_fast": 1.0 / 3.0, "p_slow": 1.0 / 31.0},
            "state_coupled_beta": DELAY.state_coupling_beta,
        },
        "selection_criterion": "match generated source-level mean delay 15 under frozen gates",
        "calibration_seed_ids": list(RUN.calibration_seeds),
        "geometric_probability": p_geom,
        "mixture_weight_fast": w_mix,
        "state_coupled_intercept": intercept,
        "calibration_metrics": {
            "pooled_generated_means": means,
            "pooled_q90": q90,
            "state_delay_spearman": coupling,
            "matched_mean_gate": mean_gate,
            "pairwise_mean_gate": pair_gate,
            "mixture_tail_gate": tail_gate,
            "state_coupling_gate": coupling_gate,
        },
        "evaluation_seed_overlap": bool(
            set(RUN.calibration_seeds).intersection(RUN.evaluation_seeds)
        ),
        "generated_at": utc_now(),
    }


def _temporary_bundle(path, delay) -> SharedPathBundle:
    tape = np.zeros(STRUCTURAL.horizon, dtype=float)
    payload_hash = hash_payload({"path": path.path_hash, "delay": delay.delay_path_hash})
    return SharedPathBundle(
        seed=path.seed,
        mechanism_id="systematic_misbinding",
        structural_path=path,
        delay_path=delay,
        learner_uniform_tape=tape,
        learner_uniform_tape_id="calibration_only",
        learner_uniform_tape_hash="calibration_only",
        bundle_id=f"calibration:{payload_hash[:16]}",
        bundle_hash=payload_hash,
    )


def calibrate_misbinding(structural_config) -> dict[str, Any]:
    candidates = [20, 30, 45]
    records = []
    for block_length in candidates:
        affected_parts = []
        margin_parts = []
        for seed in RUN.calibration_seeds:
            path = generate_systematic_misbinding_path(
                structural_config, seed, block_length=block_length
            )
            delay = generate_fixed_delay(path, DELAY.fixed_delay)
            bundle = _temporary_bundle(path, delay)
            route = build_arrival_assigned_route_map(bundle)
            eval_loss = path.structural_loss_matrix[path.source_rounds >= 0]
            reversals = ranking_reversal(route.route_loss_matrix, eval_loss)
            margins = reversal_margin(route.route_loss_matrix, eval_loss)
            affected_parts.append(reversals)
            margin_parts.append(margins[reversals])
        affected = np.concatenate(affected_parts)
        margins = np.concatenate([x for x in margin_parts if x.size])
        metrics = {
            "affected_round_fraction": float(np.mean(affected)),
            "q10_reversal_margin": float(np.quantile(margins, 0.10)),
            "near_zero_reversal_margin_share": float(np.mean(margins < 0.05)),
        }
        passed = bool(
            0.30 <= metrics["affected_round_fraction"] <= 0.60
            and metrics["q10_reversal_margin"] >= 0.20
            and metrics["near_zero_reversal_margin_share"] <= 0.05
        )
        records.append(
            {
                "block_length": block_length,
                "metrics": metrics,
                "passes_gates": passed,
            }
        )
    passing = [record for record in records if record["passes_gates"]]
    if not passing:
        raise CalibrationError(f"No systematic-misbinding block length passed: {records}")
    passing.sort(
        key=lambda record: (
            -abs(record["metrics"]["affected_round_fraction"] - 0.5),
            record["block_length"],
        ),
        reverse=True,
    )
    selected = passing[0]
    return {
        "experiment_id": EXPERIMENT_ID,
        "artifact_id": "exp1_misbinding_calibration",
        "candidate_set": candidates,
        "selection_criterion": (
            "pass persistent reversal-margin gates; select affected fraction closest to 0.5, "
            "then larger block length"
        ),
        "calibration_seed_ids": list(RUN.calibration_seeds),
        "selected_block_length": selected["block_length"],
        "calibration_metrics": records,
        "evaluation_seed_overlap": bool(
            set(RUN.calibration_seeds).intersection(RUN.evaluation_seeds)
        ),
        "generated_at": utc_now(),
    }


def run_calibration(force: bool = False) -> dict[str, Any]:
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    master_path = CALIBRATION_DIR / "exp1_calibration_manifest.json"
    if master_path.exists() and not force:
        # Idempotent no-op when the bundled/frozen calibration already matches this
        # package-local scientific source tree. We never overwrite existing artifacts.
        manifest = json.loads(master_path.read_text(encoding="utf-8"))
        current_lineage = code_lineage(PROJECT_ROOT)
        if (
            manifest.get("calibration_status") == "PASS"
            and manifest.get("code_lineage") == current_lineage
        ):
            structural = json.loads((CALIBRATION_DIR / "exp1_structural_calibration.json").read_text(encoding="utf-8"))
            context = json.loads((CALIBRATION_DIR / "exp1_context_partition.json").read_text(encoding="utf-8"))
            delay = json.loads((CALIBRATION_DIR / "exp1_delay_calibration.json").read_text(encoding="utf-8"))
            misbinding = json.loads((CALIBRATION_DIR / "exp1_misbinding_calibration.json").read_text(encoding="utf-8"))
            artifacts = {"structural": structural, "context": context, "delay": delay, "misbinding": misbinding}
            actual_hashes = {key: hash_payload(payload) for key, payload in artifacts.items()}
            if manifest.get("artifact_hashes") != actual_hashes:
                raise CalibrationError(
                    "Existing calibration claims the current code lineage but its artifact hashes do not match. "
                    "Do not continue; inspect the calibration directory."
                )
            return {"manifest": manifest, **artifacts, "already_valid": True}
        raise CalibrationError(
            f"Calibration already exists at {master_path} but belongs to a different code lineage. "
            "Use --force only after an approved change memo."
        )
    structural_artifact, selected_paths = calibrate_structural()
    selected_structural = replace(
        STRUCTURAL,
        ar_coefficient=float(structural_artifact["selected_value"]["ar_coefficient"]),
        innovation_sd=float(structural_artifact["selected_value"]["innovation_sd"]),
    )
    # Rebuild selected paths from the explicit selected configuration.
    selected_paths = [
        generate_smooth_bounded_ar1_path(selected_structural, seed)
        for seed in RUN.calibration_seeds
    ]
    context_artifact = calibrate_context(selected_paths)
    delay_artifact = calibrate_delay(selected_paths)
    misbinding_artifact = calibrate_misbinding(selected_structural)
    artifacts = {
        "structural": structural_artifact,
        "context": context_artifact,
        "delay": delay_artifact,
        "misbinding": misbinding_artifact,
    }
    code = git_commit(PROJECT_ROOT)
    lineage = code_lineage(PROJECT_ROOT)
    effective_hash = config_hash(structural=selected_structural)
    for key, payload in artifacts.items():
        payload["code_commit"] = code
        payload["code_lineage"] = lineage
        payload["config_hash"] = effective_hash
        atomic_write_json(CALIBRATION_DIR / f"exp1_{'context_partition' if key == 'context' else key + '_calibration'}.json", payload)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "calibration_status": "PASS",
        "paper_result": False,
        "calibration_seed_ids": list(RUN.calibration_seeds),
        "evaluation_seed_ids": list(RUN.evaluation_seeds),
        "evaluation_seed_overlap": False,
        "effective_structural_config": asdict(selected_structural),
        "effective_config_hash": effective_hash,
        "code_commit": code,
        "code_lineage": lineage,
        "artifact_hashes": {key: hash_payload(payload) for key, payload in artifacts.items()},
        "generated_at": utc_now(),
    }
    atomic_write_json(master_path, manifest)
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        STATUS_DIR / "calibration_status.json",
        {
            "stage": "calibration",
            "status": "PASS",
            "paper_result": False,
            "manifest": "calibration/exp1_calibration_manifest.json",
            "calibration_manifest_hash": hash_payload(manifest),
            "code_commit": code,
            "code_lineage": lineage,
            "config_hash": effective_hash,
            "generated_at": utc_now(),
        },
    )
    return {"manifest": manifest, **artifacts}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = run_calibration(force=args.force)
    print("CALIBRATION_ALREADY_VALID" if result.get("already_valid") else "CALIBRATION_COMPLETE")
    print(f"selected_structural={result['structural']['selected_value']}")
    print(f"delay={result['delay']['calibration_metrics']}")
    print(f"misbinding_block={result['misbinding']['selected_block_length']}")
    print(f"manifest={CALIBRATION_DIR / 'exp1_calibration_manifest.json'}")


if __name__ == "__main__":
    main()

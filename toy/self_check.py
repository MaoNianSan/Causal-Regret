#!/usr/bin/env python3
"""Strict semantic validation for Toy experiment artifacts.

The checker validates products of an executed simulation rather than generic
metadata alone. It rejects skipped backends, incomplete designs, nonfinite
summaries, inconsistent source--arrival records, unshared state/delay paths,
and failed zero-delay invariants.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from io_utils import compute_config_hash

EXPECTED_METHODS = {"oracle", "naive", "causal_labelled"}
EXPECTED_DELAY_SETTINGS = {
    "zero": "0_delay",
    "geometric": "geom_0.15",
    "piecewise": "piece_0.6to0.15",
    "mixture": "mixed_geom_0.6+0.1_w0.2",
}
NONFINITE_LITERALS = {
    "nan",
    "+nan",
    "-nan",
    "inf",
    "+inf",
    "-inf",
    "infinity",
    "+infinity",
    "-infinity",
}
TOL = 1e-9


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strictly audit Toy run outputs.")
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--mode", choices=["fast", "full", "all"], default="fast")
    return parser.parse_args()


def resolve_output_root(base: Path, output_dir: str, mode: str) -> Path:
    candidate = Path(output_dir)
    return (
        (candidate if candidate.is_absolute() else base / candidate) / mode
    ).resolve()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def require_nonempty_file(path: Path, errors: list[str]) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        errors.append(f"Missing or empty artifact: {path}")
        return False
    return True


def as_float(value: Any) -> float:
    if value is None:
        raise ValueError("missing numeric value")
    text = str(value).strip()
    if text.lower() in NONFINITE_LITERALS or text in {"", "NA", "N/A", "None", "null"}:
        raise ValueError(f"invalid numeric literal: {text!r}")
    result = float(text)
    if not math.isfinite(result):
        raise ValueError(f"nonfinite numeric value: {text!r}")
    return result


def as_int(value: Any) -> int:
    numeric = as_float(value)
    if not numeric.is_integer():
        raise ValueError(f"expected integer, found {value!r}")
    return int(numeric)


def is_truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def almost_equal(left: float, right: float, tolerance: float = TOL) -> bool:
    return abs(float(left) - float(right)) <= tolerance


def check_numeric_csv(path: Path, errors: list[str]) -> None:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for line_no, row in enumerate(csv.DictReader(handle), start=2):
                for key, value in row.items():
                    if (
                        value is not None
                        and value.strip().lower() in NONFINITE_LITERALS
                    ):
                        errors.append(
                            f"Nonfinite literal in {path.name}:{line_no}:{key}={value!r}"
                        )
                        return
    except Exception as exc:
        errors.append(f"Cannot scan {path}: {exc}")


def require_columns(
    rows: list[dict[str, str]], required: set[str], label: str, errors: list[str]
) -> bool:
    if not rows:
        errors.append(f"{label} has no data rows")
        return False
    missing = required.difference(rows[0])
    if missing:
        errors.append(f"{label} is missing columns: {sorted(missing)}")
        return False
    return True


def check_fast_raw(
    raw_dir: Path,
    seed_rows: list[dict[str, str]],
    seeds: list[int],
    delay_settings: set[str],
    config: dict[str, Any],
    errors: list[str],
) -> None:
    """Check raw source/arrival/step records and their cross-table invariants."""
    try:
        delay_rows = read_rows(raw_dir / "delay_schedule.csv")
        arrival_rows = read_rows(raw_dir / "arrival_log.csv")
        step_rows = read_rows(raw_dir / "step_log.csv")
        diagnostic_rows = read_rows(raw_dir / "diagnostic_step_log.csv")
    except Exception as exc:
        errors.append(f"Cannot read fast raw logs: {exc}")
        return

    T = int(config["T"])
    D_max = int(config["D_max"])
    expected_count = len(seeds) * len(delay_settings) * len(EXPECTED_METHODS) * T
    for label, rows in {
        "delay schedule": delay_rows,
        "step log": step_rows,
        "diagnostic step log": diagnostic_rows,
    }.items():
        if len(rows) != expected_count:
            errors.append(
                f"{label} row count mismatch: got {len(rows)}, expected {expected_count}"
            )

    required_delay = {
        "run_id",
        "seed",
        "source_t",
        "delay_setting",
        "method",
        "source_state",
        "source_action",
        "source_optimal_action",
        "source_loss",
        "delay_tau",
        "arrival_t",
        "is_censored",
        "censor_reason",
    }
    required_step = {
        "run_id",
        "seed",
        "t",
        "delay_setting",
        "method",
        "action_selected",
        "optimal_action_current",
        "loss_selected_current",
        "loss_optimal_current",
        "instant_causal_regret",
        "cumulative_causal_regret",
        "delay_tau",
        "arrival_t",
        "is_censored",
        "current_state",
    }
    required_arrival = {
        "run_id",
        "seed",
        "clock_t",
        "source_t",
        "delay_tau",
        "arrival_t",
        "method",
        "delay_setting",
        "observed_loss",
        "source_action",
        "current_action",
        "current_state",
        "source_state",
        "source_state_distance",
        "source_optimal_action",
        "current_optimal_action",
        "ranking_reversal",
    }
    required_diagnostic = {
        "run_id",
        "seed",
        "t",
        "delay_setting",
        "method",
        "arrival_batch_size",
        "current_state",
        "optimal_action_current",
        "arrival_rate_so_far",
        "cumulative_causal_regret",
    }
    if not (
        require_columns(delay_rows, required_delay, "delay_schedule.csv", errors)
        and require_columns(step_rows, required_step, "step_log.csv", errors)
        and require_columns(arrival_rows, required_arrival, "arrival_log.csv", errors)
        and require_columns(
            diagnostic_rows, required_diagnostic, "diagnostic_step_log.csv", errors
        )
    ):
        return

    expected_run_keys = {
        (seed, delay, method)
        for seed in seeds
        for delay in delay_settings
        for method in EXPECTED_METHODS
    }
    expected_event_keys = {
        (seed, delay, method, t)
        for seed, delay, method in expected_run_keys
        for t in range(1, T + 1)
    }

    delay_by_run_t: dict[tuple[str, int], dict[str, str]] = {}
    delay_event_keys: set[tuple[int, str, str, int]] = set()
    shared_delay: dict[tuple[int, str, int], set[int]] = defaultdict(set)
    shared_state: dict[tuple[int, str, int], set[tuple[float, int]]] = defaultdict(set)
    noncensored_events: set[tuple[str, int]] = set()
    summary_from_raw: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "delay_sum": 0.0,
            "scheduled": 0.0,
            "censored": 0.0,
            "arrived": 0.0,
            "ranking_sum": 0.0,
            "ranking_n": 0.0,
        }
    )

    for row in delay_rows:
        try:
            run_id = row["run_id"]
            seed = as_int(row["seed"])
            t = as_int(row["source_t"])
            delay_setting = row["delay_setting"]
            method = row["method"]
            delay_tau = as_int(row["delay_tau"])
            arrival_t = as_int(row["arrival_t"])
            source_state = as_float(row["source_state"])
            source_action = as_int(row["source_action"])
            source_optimal = as_int(row["source_optimal_action"])
            source_loss = as_float(row["source_loss"])
            censored = is_truthy(row["is_censored"])
            event_key = (seed, delay_setting, method, t)
            if event_key in delay_event_keys:
                errors.append(f"duplicate delay event: {event_key}")
                break
            delay_event_keys.add(event_key)
            if event_key not in expected_event_keys:
                errors.append(f"unexpected delay event: {event_key}")
                break
            if delay_tau < 0 or t < 1 or t > T:
                errors.append(f"invalid source time or delay in {event_key}")
                break
            if arrival_t != t + delay_tau:
                errors.append(
                    f"delay arithmetic fails for {event_key}: arrival_t != source_t + delay_tau"
                )
                break
            should_be_censored = delay_tau > D_max or arrival_t > T
            if censored != should_be_censored:
                errors.append(f"incorrect censoring flag for {event_key}")
                break
            expected_reason = (
                "delay_exceeds_Dmax"
                if delay_tau > D_max
                else ("arrival_out_of_horizon" if arrival_t > T else "none")
            )
            if row["censor_reason"] != expected_reason:
                errors.append(
                    f"incorrect censor reason for {event_key}: {row['censor_reason']!r}"
                )
                break
            state_clip = float(config.get("state_clip", 1.0))
            if abs(source_state) > state_clip + TOL:
                errors.append(f"source state escapes configured clip for {event_key}")
                break
            if source_loss < -TOL:
                errors.append(f"negative structural loss for {event_key}")
                break
            delay_by_run_t[(run_id, t)] = row
            shared_delay[(seed, delay_setting, t)].add(delay_tau)
            shared_state[(seed, delay_setting, t)].add((source_state, source_optimal))
            metrics = summary_from_raw[run_id]
            metrics["delay_sum"] += delay_tau
            metrics["scheduled"] += 1.0
            metrics["censored"] += float(censored)
            if not censored:
                noncensored_events.add((run_id, t))
        except Exception as exc:
            errors.append(f"invalid delay schedule row: {exc}")
            break

    if delay_event_keys != expected_event_keys:
        errors.append(
            "delay schedule does not cover the exact seed-delay-method-time design"
        )
    if any(len(values) != 1 for values in shared_delay.values()):
        errors.append(
            "delay paths are not shared across methods for a seed/delay/timestep"
        )
    if any(len(values) != 1 for values in shared_state.values()):
        errors.append(
            "latent state paths are not shared across methods for a seed/delay/timestep"
        )

    step_by_run_t: dict[tuple[str, int], dict[str, str]] = {}
    step_event_keys: set[tuple[int, str, str, int]] = set()
    zero_delay_steps: dict[tuple[int, int, str], dict[str, str]] = {}
    for row in step_rows:
        try:
            run_id = row["run_id"]
            seed = as_int(row["seed"])
            t = as_int(row["t"])
            delay_setting = row["delay_setting"]
            method = row["method"]
            event_key = (seed, delay_setting, method, t)
            if event_key in step_event_keys:
                errors.append(f"duplicate step event: {event_key}")
                break
            step_event_keys.add(event_key)
            if event_key not in expected_event_keys:
                errors.append(f"unexpected step event: {event_key}")
                break
            delay_row = delay_by_run_t.get((run_id, t))
            if delay_row is None:
                errors.append(f"step event has no matching source event: {event_key}")
                break
            for name in [
                "action_selected",
                "optimal_action_current",
                "delay_tau",
                "arrival_t",
            ]:
                as_int(row[name])
            for name in [
                "loss_selected_current",
                "loss_optimal_current",
                "instant_causal_regret",
                "cumulative_causal_regret",
                "current_state",
                "arrival_rate_so_far",
            ]:
                as_float(row[name])
            if (
                as_float(row["loss_selected_current"]) < -TOL
                or as_float(row["loss_optimal_current"]) < -TOL
            ):
                errors.append(f"negative loss in step log for {event_key}")
                break
            if as_float(row["instant_causal_regret"]) < -TOL:
                errors.append(f"negative causal regret in step log for {event_key}")
                break
            if not almost_equal(
                as_float(row["current_state"]), as_float(delay_row["source_state"])
            ):
                errors.append(f"source state and step state disagree for {event_key}")
                break
            if as_int(row["action_selected"]) != as_int(delay_row["source_action"]):
                errors.append(f"source action and step action disagree for {event_key}")
                break
            if as_int(row["optimal_action_current"]) != as_int(
                delay_row["source_optimal_action"]
            ):
                errors.append(
                    f"source optimum and step optimum disagree for {event_key}"
                )
                break
            if not almost_equal(
                as_float(row["loss_selected_current"]),
                as_float(delay_row["source_loss"]),
            ):
                errors.append(f"source loss and step loss disagree for {event_key}")
                break
            if as_int(row["delay_tau"]) != as_int(delay_row["delay_tau"]) or as_int(
                row["arrival_t"]
            ) != as_int(delay_row["arrival_t"]):
                errors.append(f"delay schedule and step log disagree for {event_key}")
                break
            if is_truthy(row["is_censored"]) != is_truthy(delay_row["is_censored"]):
                errors.append(f"censor flag disagreement for {event_key}")
                break
            if not 0.0 <= as_float(row["arrival_rate_so_far"]) <= 1.0:
                errors.append(f"arrival rate outside [0,1] for {event_key}")
                break
            step_by_run_t[(run_id, t)] = row
            if delay_setting == "0_delay" and method in {"naive", "causal_labelled"}:
                zero_delay_steps[(seed, t, method)] = row
        except Exception as exc:
            errors.append(f"invalid step log row: {exc}")
            break

    if step_event_keys != expected_event_keys:
        errors.append("step log does not cover the exact seed-delay-method-time design")

    for seed in seeds:
        for t in range(1, T + 1):
            naive = zero_delay_steps.get((seed, t, "naive"))
            causal = zero_delay_steps.get((seed, t, "causal_labelled"))
            if naive is None or causal is None:
                errors.append(f"missing zero-delay step pair for seed={seed}, t={t}")
                break
            for field in ["action_selected", "optimal_action_current"]:
                if as_int(naive[field]) != as_int(causal[field]):
                    errors.append(
                        f"zero-delay action mismatch for seed={seed}, t={t}, field={field}"
                    )
                    break
            for field in [
                "instant_causal_regret",
                "cumulative_causal_regret",
                "current_state",
            ]:
                if not almost_equal(as_float(naive[field]), as_float(causal[field])):
                    errors.append(
                        f"zero-delay trajectory mismatch for seed={seed}, t={t}, field={field}"
                    )
                    break

    arrival_keys: set[tuple[str, int]] = set()
    for row in arrival_rows:
        try:
            run_id = row["run_id"]
            source_t = as_int(row["source_t"])
            key = (run_id, source_t)
            if key in arrival_keys:
                errors.append(f"duplicate arrived source event: {key}")
                break
            arrival_keys.add(key)
            delay_row = delay_by_run_t.get(key)
            if delay_row is None:
                errors.append(f"arrival log references unknown source event: {key}")
                break
            if is_truthy(delay_row["is_censored"]):
                errors.append(
                    f"censored source event incorrectly appears in arrival log: {key}"
                )
                break
            if as_int(row["clock_t"]) != as_int(delay_row["arrival_t"]):
                errors.append(f"arrival clock mismatch for {key}")
                break
            for field in [
                "delay_tau",
                "arrival_t",
                "source_action",
                "source_optimal_action",
            ]:
                if as_int(row[field]) != as_int(delay_row[field]):
                    errors.append(f"arrival/source mismatch for {key}, field={field}")
                    break
            if not almost_equal(
                as_float(row["observed_loss"]), as_float(delay_row["source_loss"])
            ):
                errors.append(f"arrival/source loss mismatch for {key}")
                break
            if not almost_equal(
                as_float(row["source_state"]), as_float(delay_row["source_state"])
            ):
                errors.append(f"arrival/source state mismatch for {key}")
                break
            if as_int(row["ranking_reversal"]) != int(
                as_int(row["source_optimal_action"])
                != as_int(row["current_optimal_action"])
            ):
                errors.append(f"incorrect ranking-reversal flag for {key}")
                break
            actual_distance = abs(
                as_float(row["current_state"]) - as_float(row["source_state"])
            )
            if not almost_equal(
                as_float(row["source_state_distance"]), actual_distance
            ):
                errors.append(f"incorrect source-state distance for {key}")
                break
            metrics = summary_from_raw[run_id]
            metrics["arrived"] += 1.0
            metrics["ranking_sum"] += as_int(row["ranking_reversal"])
            metrics["ranking_n"] += 1.0
        except Exception as exc:
            errors.append(f"invalid arrival log row: {exc}")
            break

    if arrival_keys != noncensored_events:
        errors.append(
            "arrival log does not contain exactly the uncensored source events"
        )

    diagnostic_event_keys: set[tuple[int, str, str, int]] = set()
    for row in diagnostic_rows:
        try:
            event_key = (
                as_int(row["seed"]),
                row["delay_setting"],
                row["method"],
                as_int(row["t"]),
            )
            if event_key in diagnostic_event_keys:
                errors.append(f"duplicate diagnostic event: {event_key}")
                break
            diagnostic_event_keys.add(event_key)
            if event_key not in expected_event_keys:
                errors.append(f"unexpected diagnostic event: {event_key}")
                break
            if as_int(row["arrival_batch_size"]) < 0:
                errors.append(f"negative arrival batch size in {event_key}")
                break
            for field in [
                "current_state",
                "arrival_rate_so_far",
                "cumulative_causal_regret",
            ]:
                as_float(row[field])
        except Exception as exc:
            errors.append(f"invalid diagnostic row: {exc}")
            break
    if diagnostic_event_keys != expected_event_keys:
        errors.append(
            "diagnostic step log does not cover the exact seed-delay-method-time design"
        )

    summary_by_run_id = {row["run_id"]: row for row in seed_rows}
    for (run_id, t), step_row in step_by_run_t.items():
        if t != T:
            continue
        summary_row = summary_by_run_id.get(run_id)
        if summary_row is None:
            errors.append(f"missing seed summary for run_id={run_id}")
            continue
        metrics = summary_from_raw[run_id]
        if not almost_equal(
            as_float(summary_row["final_Rc"]),
            as_float(step_row["cumulative_causal_regret"]),
        ):
            errors.append(
                f"final regret summary disagrees with step log for run_id={run_id}"
            )
        if not almost_equal(
            as_float(summary_row["arrival_rate"]), metrics["arrived"] / T
        ):
            errors.append(
                f"arrival-rate summary disagrees with raw logs for run_id={run_id}"
            )
        if not almost_equal(
            as_float(summary_row["censor_rate"]), metrics["censored"] / T
        ):
            errors.append(
                f"censor-rate summary disagrees with raw logs for run_id={run_id}"
            )
        if not almost_equal(
            as_float(summary_row["mean_delay"]), metrics["delay_sum"] / T
        ):
            errors.append(
                f"mean-delay summary disagrees with raw logs for run_id={run_id}"
            )
        expected_ranking = (
            metrics["ranking_sum"] / metrics["ranking_n"]
            if metrics["ranking_n"]
            else 0.0
        )
        if not almost_equal(
            as_float(summary_row["ranking_reversal_rate"]), expected_ranking
        ):
            errors.append(
                f"ranking-reversal summary disagrees with raw logs for run_id={run_id}"
            )


def check_mode(output_root: Path, mode: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    raw_dir = output_root / "raw"
    summary_dir = output_root / "summary"
    figures_dir = output_root / "figures"
    logs_dir = output_root / "logs"

    required = [
        logs_dir / "config_snapshot.yaml",
        logs_dir / "run_metadata.json",
        logs_dir / "run_manifest.csv",
        logs_dir / "method_registry.csv",
        summary_dir / "toy_seed_summary.csv",
        summary_dir / "toy_method_summary.csv",
        summary_dir / "toy_trajectory_summary.csv",
        figures_dir / "toy_selected_trajectories_data.csv",
        figures_dir / "toy_full_trajectories_data.csv",
        figures_dir / "toy_selected_trajectories.pdf",
        figures_dir / "toy_selected_trajectories.png",
        figures_dir / "toy_full_trajectories.pdf",
        figures_dir / "toy_full_trajectories.png",
    ]
    if mode == "fast":
        required.extend(
            [
                raw_dir / "delay_schedule.csv",
                raw_dir / "arrival_log.csv",
                raw_dir / "step_log.csv",
                raw_dir / "diagnostic_step_log.csv",
            ]
        )
    if not all(require_nonempty_file(path, errors) for path in required):
        return False, errors

    try:
        with (logs_dir / "config_snapshot.yaml").open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle)
        if not isinstance(config, dict):
            raise ValueError("config snapshot is not a mapping")
        if config.get("run_mode") != mode:
            errors.append(
                f"config snapshot mode mismatch: expected {mode}, found {config.get('run_mode')!r}"
            )
        seeds = [int(x) for x in config.get("seeds", [])]
        if len(seeds) != len(set(seeds)):
            errors.append("config snapshot repeats seeds")
        if mode == "fast" and len(seeds) != 3:
            errors.append(f"fast mode must contain exactly 3 seeds; found {len(seeds)}")
        if mode == "full" and len(seeds) < 3:
            errors.append(
                f"full mode must contain at least 3 seeds; found {len(seeds)}"
            )
        expected_delay_settings = {
            EXPECTED_DELAY_SETTINGS[group] for group in config.get("delay_settings", [])
        }
        if not expected_delay_settings:
            errors.append("config snapshot contains no selected delay settings")
        configured_methods = set(config.get("methods", []))
        if configured_methods != EXPECTED_METHODS:
            errors.append(
                f"configured methods mismatch: expected {sorted(EXPECTED_METHODS)}, found {sorted(configured_methods)}"
            )
        if config.get("state_clip", 1.0) <= 0 or config.get("state_sigma", 0.10) <= 0:
            errors.append("state-process configuration is invalid")
        if not (-1.0 < float(config.get("state_rho", 0.98)) < 1.0):
            errors.append("state_rho lies outside (-1, 1)")
        config_hash = compute_config_hash(config)
    except Exception as exc:
        errors.append(f"Invalid config snapshot: {exc}")
        return False, errors

    try:
        metadata = json.loads(
            (logs_dir / "run_metadata.json").read_text(encoding="utf-8")
        )
        if metadata.get("status") != "success":
            errors.append(
                f"run metadata status is not success: {metadata.get('status')!r}"
            )
        if metadata.get("backend_status") != "executed":
            errors.append(
                f"run backend was not executed: {metadata.get('backend_status')!r}"
            )
        if metadata.get("mode") != mode:
            errors.append(
                f"run metadata mode mismatch: expected {mode}, found {metadata.get('mode')!r}"
            )
        if metadata.get("config_hash") != config_hash:
            errors.append(
                "run metadata config hash does not match the saved configuration"
            )
        if metadata.get("feedback_timing") != "post_decision":
            errors.append("run metadata does not declare post-decision feedback timing")
        state_process = metadata.get("state_process", {})
        if state_process.get("type") != "clipped_ar1":
            errors.append(
                "run metadata does not declare the clipped AR(1) state process"
            )
    except Exception as exc:
        errors.append(f"Invalid run metadata: {exc}")

    for path in [
        summary_dir / "toy_seed_summary.csv",
        summary_dir / "toy_method_summary.csv",
        summary_dir / "toy_trajectory_summary.csv",
        figures_dir / "toy_selected_trajectories_data.csv",
        figures_dir / "toy_full_trajectories_data.csv",
    ]:
        check_numeric_csv(path, errors)

    try:
        registry_methods = {
            row["method"] for row in read_rows(logs_dir / "method_registry.csv")
        }
        if registry_methods != EXPECTED_METHODS:
            errors.append(
                f"method registry mismatch: expected {sorted(EXPECTED_METHODS)}, found {sorted(registry_methods)}"
            )
    except Exception as exc:
        errors.append(f"Cannot validate method registry: {exc}")

    try:
        run_rows = read_rows(logs_dir / "run_manifest.csv")
        expected_run_count = (
            len(seeds) * len(expected_delay_settings) * len(EXPECTED_METHODS)
        )
        expected_keys = {
            (seed, delay, method)
            for seed in seeds
            for delay in expected_delay_settings
            for method in EXPECTED_METHODS
        }
        run_keys = {
            (as_int(row["seed"]), row["delay_setting"], row["method"])
            for row in run_rows
        }
        if len(run_rows) != expected_run_count or run_keys != expected_keys:
            errors.append(
                "run manifest does not cover exactly the effective seed-delay-method design"
            )
        if len(run_keys) != len(run_rows):
            errors.append("run manifest contains duplicate seed-delay-method rows")
        for row in run_rows:
            if row.get("mode") != mode or row.get("config_hash") != config_hash:
                errors.append(
                    f"run manifest metadata mismatch in run_id={row.get('run_id')}"
                )
                break
    except Exception as exc:
        errors.append(f"Cannot validate run manifest: {exc}")

    seed_rows: list[dict[str, str]] = []
    try:
        seed_rows = read_rows(summary_dir / "toy_seed_summary.csv")
        expected_keys = {
            (seed, delay, method)
            for seed in seeds
            for delay in expected_delay_settings
            for method in EXPECTED_METHODS
        }
        keys = {
            (as_int(row["seed"]), row["delay_setting"], row["method"])
            for row in seed_rows
        }
        if len(seed_rows) != len(expected_keys) or keys != expected_keys:
            errors.append(
                "seed summary does not cover exactly the configured seed-delay-method design"
            )
        required_numeric = {
            "mean_delay",
            "median_delay",
            "p90_delay",
            "max_delay",
            "arrival_rate",
            "censor_rate",
            "ranking_reversal_rate",
            "source_state_distance_mean",
            "source_state_distance_sum",
            "source_state_distance_p90",
            "final_Rc",
            "normalized_final_Rc",
            "auc_causal_regret",
            "mean_instant_causal_regret",
            "runtime_seconds",
        }
        if not require_columns(
            seed_rows,
            required_numeric
            | {"run_id", "seed", "delay_setting", "method", "mode", "config_hash"},
            "seed summary",
            errors,
        ):
            return False, errors
        for row in seed_rows:
            if row.get("mode") != mode or row.get("config_hash") != config_hash:
                errors.append("seed summary contains incorrect metadata")
                break
            for key in required_numeric:
                as_float(row[key])
            for rate_field in ["arrival_rate", "censor_rate", "ranking_reversal_rate"]:
                if not 0.0 <= as_float(row[rate_field]) <= 1.0:
                    errors.append(f"{rate_field} falls outside [0,1]")
                    break
            state_clip = float(config.get("state_clip", 1.0))
            if (
                not 0.0
                <= as_float(row["source_state_distance_mean"])
                <= 2.0 * state_clip + TOL
            ):
                errors.append(
                    "source-state distance mean lies outside the bounded state support"
                )
                break
            if (
                not 0.0
                <= as_float(row["source_state_distance_p90"])
                <= 2.0 * state_clip + TOL
            ):
                errors.append(
                    "source-state distance p90 lies outside the bounded state support"
                )
                break
            if (
                as_float(row["final_Rc"]) < -TOL
                or as_float(row["mean_instant_causal_regret"]) < -TOL
            ):
                errors.append("seed summary contains negative structural causal regret")
                break
            if row["method"] == "oracle" and abs(as_float(row["final_Rc"])) > TOL:
                errors.append("oracle final structural causal regret is not zero")
                break

        by_seed_delay: dict[tuple[int, str], dict[str, float]] = defaultdict(dict)
        for row in seed_rows:
            by_seed_delay[(as_int(row["seed"]), row["delay_setting"])][
                row["method"]
            ] = as_float(row["final_Rc"])
        for (seed, delay), values in by_seed_delay.items():
            if delay == "0_delay" and not almost_equal(
                values["naive"], values["causal_labelled"]
            ):
                errors.append(f"zero-delay naive/causal mismatch for seed={seed}")
                break
    except Exception as exc:
        errors.append(f"Cannot validate seed summary: {exc}")

    try:
        trajectory_rows = read_rows(summary_dir / "toy_trajectory_summary.csv")
        expected_t = set(range(1, int(config["T"]) + 1))
        trajectories: dict[tuple[str, str], set[int]] = defaultdict(set)
        values_by_key: dict[tuple[str, str, int], float] = {}
        for row in trajectory_rows:
            t = as_int(row["t"])
            trajectories[(row["delay_setting"], row["method"])].add(t)
            for key in [
                "mean_cumulative_Rc",
                "se_cumulative_Rc",
                "ci95_low",
                "ci95_high",
            ]:
                as_float(row[key])
            if as_float(row["mean_cumulative_Rc"]) < -TOL:
                errors.append("trajectory summary contains negative cumulative regret")
                break
            values_by_key[(row["delay_setting"], row["method"], t)] = as_float(
                row["mean_cumulative_Rc"]
            )
        for delay in expected_delay_settings:
            for method in EXPECTED_METHODS:
                if trajectories[(delay, method)] != expected_t:
                    errors.append(
                        f"trajectory coverage is incomplete for delay={delay}, method={method}"
                    )
        for t in expected_t:
            if not almost_equal(
                values_by_key[("0_delay", "naive", t)],
                values_by_key[("0_delay", "causal_labelled", t)],
            ):
                errors.append(f"zero-delay trajectory mismatch at t={t}")
                break
    except Exception as exc:
        errors.append(f"Cannot validate trajectory summary: {exc}")

    try:
        selected = read_rows(figures_dir / "toy_selected_trajectories_data.csv")
        full = read_rows(figures_dir / "toy_full_trajectories_data.csv")
        if {row["delay_setting"] for row in selected} != {
            "0_delay",
            "geom_0.15",
            "piece_0.6to0.15",
        }:
            errors.append(
                "selected figure source does not contain the required three settings"
            )
        if {row["delay_setting"] for row in full} != expected_delay_settings:
            errors.append(
                "full figure source does not cover exactly the configured delay settings"
            )
    except Exception as exc:
        errors.append(f"Cannot validate figure-source tables: {exc}")

    if mode == "fast" and seed_rows:
        check_fast_raw(
            raw_dir, seed_rows, seeds, expected_delay_settings, config, errors
        )

    return not errors, errors


def main() -> None:
    args = parse_args()
    base = Path(__file__).resolve().parent
    modes = ["fast", "full"] if args.mode == "all" else [args.mode]
    all_errors: list[str] = []
    for mode in modes:
        root = resolve_output_root(base, args.output_dir, mode)
        passed, errors = check_mode(root, mode)
        if passed:
            print(f"SELF-CHECK PASSED for mode={mode}: {root}")
        else:
            print(f"SELF-CHECK FAILED for mode={mode}: {root}")
            for error in errors:
                print(f"  - {error}")
            all_errors.extend([f"{mode}: {error}" for error in errors])
    raise SystemExit(0 if not all_errors else 1)


if __name__ == "__main__":
    main()

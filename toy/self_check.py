#!/usr/bin/env python3
"""Strict semantic validation for Toy experiment artifacts.

The checker validates the products of actual simulation, not merely the
existence of generic metadata. A skipped backend, missing required artifact,
empty result table, corrupted numeric field, or inconsistent delay path fails.
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

EXPECTED_METHODS = {"oracle", "naive", "causal_labelled"}
EXPECTED_DELAY_SETTINGS = {
    "zero": "0_delay",
    "geometric": "geom_0.15",
    "piecewise": "piece_0.6to0.15",
    "mixture": "mixed_geom_0.6+0.1_w0.2",
}
NONFINITE_LITERALS = {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strictly audit Toy run outputs.")
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--mode", choices=["fast", "full", "all"], default="fast")
    return parser.parse_args()


def resolve_output_root(base: Path, output_dir: str, mode: str) -> Path:
    candidate = Path(output_dir)
    return ((candidate if candidate.is_absolute() else base / candidate) / mode).resolve()


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
    if text.lower() in NONFINITE_LITERALS or text == "":
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


def check_numeric_csv(path: Path, errors: list[str]) -> None:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for line_no, row in enumerate(csv.DictReader(handle), start=2):
                for key, value in row.items():
                    if value is not None and value.strip().lower() in NONFINITE_LITERALS:
                        errors.append(f"Nonfinite literal in {path.name}:{line_no}:{key}={value!r}")
                        return
    except Exception as exc:
        errors.append(f"Cannot scan {path}: {exc}")


def check_mode(output_root: Path, mode: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
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
        required.extend([
            raw_dir / "delay_schedule.csv",
            raw_dir / "arrival_log.csv",
            raw_dir / "step_log.csv",
            raw_dir / "diagnostic_step_log.csv",
        ])
    if not all(require_nonempty_file(path, errors) for path in required):
        return False, errors

    try:
        with (logs_dir / "config_snapshot.yaml").open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle)
        if not isinstance(config, dict):
            raise ValueError("config snapshot is not a mapping")
        if config.get("run_mode") != mode:
            errors.append(f"config snapshot mode mismatch: expected {mode}, found {config.get('run_mode')!r}")
        seeds = [int(x) for x in config.get("seeds", [])]
        if mode == "fast" and len(seeds) != 3:
            errors.append(f"fast mode must contain exactly 3 seeds; found {len(seeds)}")
        if mode == "full" and len(seeds) < 3:
            errors.append(f"full mode must contain at least 3 seeds; found {len(seeds)}")
        expected_delay_settings = {EXPECTED_DELAY_SETTINGS[group] for group in config.get("delay_settings", [])}
        if not expected_delay_settings:
            errors.append("config snapshot contains no selected delay settings")
        configured_methods = set(config.get("methods", []))
        if configured_methods != EXPECTED_METHODS:
            errors.append(f"configured methods mismatch: expected {sorted(EXPECTED_METHODS)}, found {sorted(configured_methods)}")
    except Exception as exc:
        errors.append(f"Invalid config snapshot: {exc}")
        return False, errors

    try:
        metadata = json.loads((logs_dir / "run_metadata.json").read_text(encoding="utf-8"))
        if metadata.get("status") != "success":
            errors.append(f"run metadata status is not success: {metadata.get('status')!r}")
        if metadata.get("backend_status") != "executed":
            errors.append(f"run backend was not executed: {metadata.get('backend_status')!r}")
        if metadata.get("mode") != mode:
            errors.append(f"run metadata mode mismatch: expected {mode}, found {metadata.get('mode')!r}")
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
        registry_methods = {row["method"] for row in read_rows(logs_dir / "method_registry.csv")}
        if registry_methods != EXPECTED_METHODS:
            errors.append(f"method registry mismatch: expected {sorted(EXPECTED_METHODS)}, found {sorted(registry_methods)}")
    except Exception as exc:
        errors.append(f"Cannot validate method registry: {exc}")

    try:
        run_rows = read_rows(logs_dir / "run_manifest.csv")
        expected_run_count = len(seeds) * len(expected_delay_settings) * len(EXPECTED_METHODS)
        if len(run_rows) != expected_run_count:
            errors.append(f"run manifest has {len(run_rows)} rows; expected {expected_run_count}")
        run_keys = {(as_int(row["seed"]), row["delay_setting"], row["method"]) for row in run_rows}
        if len(run_keys) != len(run_rows):
            errors.append("run manifest contains duplicate seed-delay-method rows")
        expected_keys = {(seed, delay, method) for seed in seeds for delay in expected_delay_settings for method in EXPECTED_METHODS}
        if run_keys != expected_keys:
            errors.append("run manifest seed-delay-method coverage does not match the effective design")
        for row in run_rows:
            if row.get("mode") != mode:
                errors.append(f"run manifest mode mismatch in run_id={row.get('run_id')}")
                break
    except Exception as exc:
        errors.append(f"Cannot validate run manifest: {exc}")

    try:
        seed_rows = read_rows(summary_dir / "toy_seed_summary.csv")
        keys = {(as_int(row["seed"]), row["delay_setting"], row["method"]) for row in seed_rows}
        expected_keys = {(seed, delay, method) for seed in seeds for delay in expected_delay_settings for method in EXPECTED_METHODS}
        if len(seed_rows) != len(expected_keys) or keys != expected_keys:
            errors.append("seed summary does not cover exactly the configured seed-delay-method design")
        for row in seed_rows:
            if row.get("mode") != mode:
                errors.append("seed summary contains an incorrect mode label")
                break
            for key in ["mean_delay", "arrival_rate", "final_Rc", "normalized_final_Rc", "auc_causal_regret", "runtime_seconds"]:
                as_float(row[key])
            if as_float(row["arrival_rate"]) < 0 or as_float(row["arrival_rate"]) > 1:
                errors.append("arrival_rate falls outside [0, 1]")
                break
            if row["method"] == "oracle" and abs(as_float(row["final_Rc"])) > 1e-12:
                errors.append("oracle final structural causal regret is not zero")
                break

        by_seed_delay: dict[tuple[int, str], dict[str, float]] = defaultdict(dict)
        for row in seed_rows:
            by_seed_delay[(as_int(row["seed"]), row["delay_setting"])][row["method"]] = as_float(row["final_Rc"])
        for (seed, delay), values in by_seed_delay.items():
            if delay == "0_delay" and abs(values["naive"] - values["causal_labelled"]) > 1e-9:
                errors.append(f"zero-delay naive/causal mismatch for seed={seed}")
                break
    except Exception as exc:
        errors.append(f"Cannot validate seed summary: {exc}")

    try:
        trajectory_rows = read_rows(summary_dir / "toy_trajectory_summary.csv")
        expected_t = set(range(1, int(config["T"]) + 1))
        trajectories: dict[tuple[str, str], set[int]] = defaultdict(set)
        for row in trajectory_rows:
            t = as_int(row["t"])
            trajectories[(row["delay_setting"], row["method"])].add(t)
            for key in ["mean_cumulative_Rc", "se_cumulative_Rc", "ci95_low", "ci95_high"]:
                as_float(row[key])
        for delay in expected_delay_settings:
            for method in EXPECTED_METHODS:
                if trajectories[(delay, method)] != expected_t:
                    errors.append(f"trajectory coverage is incomplete for delay={delay}, method={method}")
                    break
        # The zero-delay trajectories must agree pointwise, not merely at T.
        zero = {(as_int(row["t"]), row["method"]): as_float(row["mean_cumulative_Rc"]) for row in trajectory_rows if row["delay_setting"] == "0_delay"}
        for t in expected_t:
            if abs(zero[(t, "naive")] - zero[(t, "causal_labelled")]) > 1e-9:
                errors.append(f"zero-delay trajectory mismatch at t={t}")
                break
    except Exception as exc:
        errors.append(f"Cannot validate trajectory summary: {exc}")

    try:
        selected = read_rows(figures_dir / "toy_selected_trajectories_data.csv")
        full = read_rows(figures_dir / "toy_full_trajectories_data.csv")
        selected_delays = {row["delay_setting"] for row in selected}
        full_delays = {row["delay_setting"] for row in full}
        if not selected_delays.issubset(expected_delay_settings):
            errors.append("selected figure source contains an unconfigured delay setting")
        if full_delays != expected_delay_settings:
            errors.append("full figure source does not cover exactly the configured delay settings")
    except Exception as exc:
        errors.append(f"Cannot validate figure-source tables: {exc}")

    if mode == "fast":
        try:
            delay_rows = read_rows(raw_dir / "delay_schedule.csv")
            step_rows = read_rows(raw_dir / "step_log.csv")
            expected_raw_rows = len(seeds) * len(expected_delay_settings) * len(EXPECTED_METHODS) * int(config["T"])
            if len(delay_rows) != expected_raw_rows or len(step_rows) != expected_raw_rows:
                errors.append(f"fast raw log row count mismatch: delay={len(delay_rows)}, step={len(step_rows)}, expected={expected_raw_rows}")
            delay_paths: dict[tuple[int, str, int], set[int]] = defaultdict(set)
            for row in delay_rows:
                seed = as_int(row["seed"])
                source_t = as_int(row["source_t"])
                delay = as_int(row["delay_tau"])
                if delay < 0:
                    errors.append("negative delay in delay schedule")
                    break
                delay_paths[(seed, row["delay_setting"], source_t)].add(delay)
                if not is_truthy(row["is_censored"]):
                    if as_int(row["arrival_t"]) != source_t + delay:
                        errors.append("uncensored delay schedule violates arrival_t = source_t + delay_tau")
                        break
            if any(len(values) != 1 for values in delay_paths.values()):
                errors.append("delay paths are not shared across methods for a seed/delay/timestep")
            for row in step_rows:
                if as_int(row["t"]) < 1 or as_int(row["t"]) > int(config["T"]):
                    errors.append("step log contains out-of-range timestep")
                    break
                for key in ["instant_causal_regret", "cumulative_causal_regret", "arrival_rate_so_far"]:
                    as_float(row[key])
        except Exception as exc:
            errors.append(f"Cannot validate fast raw logs: {exc}")

    if warnings:
        errors.extend([f"WARNING: {warning}" for warning in warnings])
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

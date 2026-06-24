#!/usr/bin/env python3
"""Run the self-contained Toy delayed-feedback experiment.

`fast` uses the first three configured seeds and preserves raw diagnostic logs.
`full` uses all configured seeds and writes lightweight summaries and figures.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml

from core import CausalLearner, NaiveLearner, OracleLearner, run_one_seed
from delay import DelaySetting, build_delay_settings
from io_utils import compute_config_hash, ensure_dir, now_timestamp, write_rows_csv
from plot import generate_figures

DELAY_GROUP_TO_NAME = {
    "zero": "0_delay",
    "geometric": "geom_0.15",
    "piecewise": "piece_0.6to0.15",
    "mixture": "mixed_geom_0.6+0.1_w0.2",
}

METHOD_REGISTRY = [
    {
        "method": "oracle",
        "method_display_name": "Oracle",
        "description": "Full-information lower-bound reference; always selects the structural-time optimal action.",
    },
    {
        "method": "naive",
        "method_display_name": "Naive",
        "description": "Arrival-time binding baseline; deliberately assigns arrived feedback to the current action.",
    },
    {
        "method": "causal_labelled",
        "method_display_name": "Causal-labelled",
        "description": "Source-labelled delay-aware learner; updates the action that generated each arrived feedback item.",
    },
]

RAW_FIELDNAMES = {
    "run_manifest": [
        "run_id",
        "created_time",
        "experiment_id",
        "mode",
        "config_hash",
        "seed",
        "delay_setting",
        "method",
        "T",
        "K",
        "D_max",
        "delay_meta_type",
        "delay_meta_p",
        "delay_meta_w",
        "delay_meta_p_fast",
        "delay_meta_p_slow",
        "delay_meta_switch_t",
    ],
    "delay_schedule": [
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
    ],
    "arrival_log": [
        "run_id",
        "seed",
        "clock_t",
        "source_t",
        "delay_tau",
        "arrival_t",
        "method",
        "delay_setting",
        "batch_size_at_clock_t",
        "observed_loss",
        "source_action",
        "current_action",
        "current_state",
        "source_state",
        "source_state_distance",
        "source_optimal_action",
        "current_optimal_action",
        "ranking_reversal",
    ],
    "step_log": [
        "run_id",
        "seed",
        "t",
        "T",
        "K",
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
        "scheduled_count_so_far",
        "arrived_count_so_far",
        "arrival_rate_so_far",
        "current_state",
        "epsilon_used",
    ],
    "diagnostic_step_log": [
        "run_id",
        "seed",
        "t",
        "delay_setting",
        "method",
        "arrival_batch_size",
        "mean_source_state_distance",
        "ranking_reversal_rate_at_t",
        "current_state",
        "optimal_action_current",
        "arrival_rate_so_far",
        "cumulative_causal_regret",
    ],
}

SEED_SUMMARY_FIELDNAMES = [
    "experiment_id",
    "mode",
    "config_hash",
    "run_id",
    "seed",
    "delay_setting",
    "method",
    "T",
    "K",
    "D_max",
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
    "gain_vs_naive",
    "gain_vs_naive_pct",
    "runtime_seconds",
]

TRAJECTORY_FIELDNAMES = [
    "experiment_id",
    "mode",
    "config_hash",
    "delay_setting",
    "method",
    "t",
    "mean_cumulative_Rc",
    "se_cumulative_Rc",
    "ci95_low",
    "ci95_high",
]


class ToyCausalEnv:
    """Latent-state environment used by the Toy diagnostic.

    Actions index evenly spaced anchor states on [-1, 1]. The latent state is a
    reproducible clipped AR(1) process, so it is dynamic but remains on the
    same bounded support as the action anchors. Loss is squared distance between
    the action anchor and the current state. This intentionally simple process
    creates source-time/action binding that can change before feedback arrives
    without allowing an unbounded random walk to dominate regret magnitudes.
    """

    def __init__(
        self,
        A: list[int],
        seed: int,
        rho_state: float = 0.98,
        sigma_state: float = 0.10,
        state_clip: float = 1.0,
    ):
        if not A:
            raise ValueError("A must contain at least one action")
        if not (-1.0 < float(rho_state) < 1.0):
            raise ValueError("rho_state must lie strictly between -1 and 1")
        if float(sigma_state) <= 0.0:
            raise ValueError("sigma_state must be positive")
        if float(state_clip) <= 0.0:
            raise ValueError("state_clip must be positive")
        self.A = list(A)
        self.rng = np.random.default_rng(seed)
        self.S = 0.0
        self.rho_state = float(rho_state)
        self.sigma_state = float(sigma_state)
        self.state_clip = float(state_clip)
        denom = max(1, len(self.A) - 1)
        self.mu = {a: -1.0 + 2.0 * idx / denom for idx, a in enumerate(self.A)}

    def state(self) -> float:
        return float(self.S)

    def step(self, t: int) -> None:
        del t
        innovation = float(self.rng.normal(0.0, self.sigma_state))
        self.S = float(
            np.clip(
                self.rho_state * self.S + innovation, -self.state_clip, self.state_clip
            )
        )

    def true_loss(self, a: int, S_t: float) -> float:
        if a not in self.mu:
            raise ValueError(f"Unknown action {a}")
        diff = self.mu[a] - float(S_t)
        return float(diff * diff)

    def oracle_action(self, S_t: float) -> int:
        return min(self.A, key=lambda a: self.true_loss(a, S_t))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Toy delayed-feedback diagnostic."
    )
    parser.add_argument(
        "--config", default="config.yaml", help="YAML configuration path."
    )
    parser.add_argument("--mode", choices=["fast", "full"], default="full")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError("config.yaml must contain a YAML mapping")
    return config


def validate_config(config: dict[str, Any]) -> None:
    required = {
        "experiment_id",
        "T",
        "K",
        "D_max",
        "seeds",
        "delay_settings",
        "methods",
        "output_dir",
        "save_raw_trajectories",
        "save_summary",
        "save_figures",
        "figure_format",
        "dpi",
    }
    missing = sorted(required.difference(config))
    if missing:
        raise ValueError(f"config.yaml is missing required keys: {missing}")
    if int(config["T"]) <= 0 or int(config["K"]) < 2 or int(config["D_max"]) < 0:
        raise ValueError(
            "T must be positive, K must be >= 2, and D_max must be nonnegative"
        )
    if not isinstance(config["seeds"], list) or not config["seeds"]:
        raise ValueError("seeds must be a nonempty list")
    seeds = [int(seed) for seed in config["seeds"]]
    if len(seeds) != len(set(seeds)):
        raise ValueError("seeds must be unique")
    if len(config["delay_settings"]) != len(set(config["delay_settings"])):
        raise ValueError("delay_settings must not contain duplicates")
    if len(config["methods"]) != len(set(config["methods"])):
        raise ValueError("methods must not contain duplicates")
    rho_state = float(config.get("state_rho", 0.98))
    sigma_state = float(config.get("state_sigma", 0.10))
    state_clip = float(config.get("state_clip", 1.0))
    if not (-1.0 < rho_state < 1.0):
        raise ValueError("state_rho must lie strictly between -1 and 1")
    if sigma_state <= 0.0:
        raise ValueError("state_sigma must be positive")
    if state_clip <= 0.0:
        raise ValueError("state_clip must be positive")
    if not bool(config["save_summary"]) or not bool(config["save_figures"]):
        raise ValueError(
            "Toy artifact contract requires save_summary=true and save_figures=true"
        )
    requested_formats = set(config["figure_format"])
    if not {"pdf", "png"}.issubset(requested_formats):
        raise ValueError("figure_format must include both 'pdf' and 'png'")
    if set(config["delay_settings"]) != set(DELAY_GROUP_TO_NAME):
        raise ValueError(
            "Toy requires exactly zero, geometric, piecewise, and mixture delay settings"
        )
    invalid_groups = [
        name for name in config["delay_settings"] if name not in DELAY_GROUP_TO_NAME
    ]
    if invalid_groups:
        raise ValueError(
            f"Unsupported delay groups: {invalid_groups}; supported={sorted(DELAY_GROUP_TO_NAME)}"
        )
    expected_methods = {row["method"] for row in METHOD_REGISTRY}
    invalid_methods = [
        name for name in config["methods"] if name not in expected_methods
    ]
    if invalid_methods:
        raise ValueError(
            f"Unsupported methods: {invalid_methods}; supported={sorted(expected_methods)}"
        )
    if set(config["methods"]) != expected_methods:
        raise ValueError(
            "Toy requires exactly oracle, naive, and causal_labelled for its checked comparisons"
        )


def resolve_output_dir(root: Path, configured_output_dir: str, mode: str) -> Path:
    candidate = Path(configured_output_dir)
    output_base = candidate if candidate.is_absolute() else (root / candidate)
    return (output_base / mode).resolve()


def build_shared_delay_sequence(
    T: int, delay_setting: DelaySetting, seed: int
) -> list[int]:
    """Generate one deterministic path reused by all methods in a seed/scenario."""
    prior_state = random.getstate()
    try:
        random.seed(seed * 1009 + sum(ord(ch) for ch in delay_setting.name))
        return [int(delay_setting.sampler(t)) for t in range(1, T + 1)]
    finally:
        random.setstate(prior_state)


def prepare_directories(output_root: Path, save_raw: bool) -> dict[str, Path]:
    """Clear the target mode directory so stale artifacts cannot satisfy validation."""
    if output_root.exists():
        shutil.rmtree(output_root)
    raw_dir = ensure_dir(output_root / "raw") if save_raw else output_root / "raw"
    summary_dir = ensure_dir(output_root / "summary")
    figures_dir = ensure_dir(output_root / "figures")
    logs_dir = ensure_dir(output_root / "logs")
    return {
        "root": output_root,
        "raw": raw_dir,
        "summary": summary_dir,
        "figures": figures_dir,
        "logs": logs_dir,
    }


def write_yaml(path: Path, value: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(value, handle, sort_keys=False)


def write_json(path: Path, value: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


def learner_for_method(method: str):
    if method == "oracle":
        return OracleLearner()
    if method == "naive":
        return NaiveLearner(alpha=0.3)
    if method == "causal_labelled":
        return CausalLearner(alpha=0.3)
    raise ValueError(f"Unsupported method: {method}")


def _trajectory_rows(
    trajectory_values: dict[tuple[str, str, int], list[float]],
    experiment_id: str,
    mode: str,
    config_hash: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for (delay_setting, method, t), values in sorted(trajectory_values.items()):
        values_arr = np.asarray(values, dtype=float)
        n = len(values_arr)
        mean = float(values_arr.mean())
        se = float(values_arr.std(ddof=1) / math.sqrt(n)) if n > 1 else 0.0
        margin = 1.96 * se
        rows.append(
            {
                "experiment_id": experiment_id,
                "mode": mode,
                "config_hash": config_hash,
                "delay_setting": delay_setting,
                "method": method,
                "t": t,
                "mean_cumulative_Rc": mean,
                "se_cumulative_Rc": se,
                "ci95_low": mean - margin,
                "ci95_high": mean + margin,
            }
        )
    return rows


def _method_summary_rows(seed_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in seed_rows:
        grouped[(str(row["delay_setting"]), str(row["method"]))].append(row)
    for (delay_setting, method), group in sorted(grouped.items()):
        final = np.asarray([float(row["final_Rc"]) for row in group], dtype=float)
        n = len(final)
        mean = float(final.mean())
        std = float(final.std(ddof=1)) if n > 1 else 0.0
        se = std / math.sqrt(n) if n else 0.0
        gains = np.asarray(
            [
                float(row["gain_vs_naive_pct"])
                for row in group
                if row["gain_vs_naive_pct"] is not None
            ],
            dtype=float,
        )
        gain_mean = float(gains.mean()) if len(gains) else None
        gain_se = (
            float(gains.std(ddof=1) / math.sqrt(len(gains)))
            if len(gains) > 1
            else (0.0 if len(gains) == 1 else None)
        )
        rows.append(
            {
                "experiment_id": group[0]["experiment_id"],
                "mode": group[0]["mode"],
                "config_hash": group[0]["config_hash"],
                "delay_setting": delay_setting,
                "method": method,
                "n_seeds": n,
                "mean_final_Rc": mean,
                "std_final_Rc": std,
                "se_final_Rc": se,
                "ci95_low": mean - 1.96 * se,
                "ci95_high": mean + 1.96 * se,
                "mean_gain_vs_naive_pct": gain_mean,
                "gain_ci95_low": (
                    (gain_mean - 1.96 * gain_se)
                    if gain_mean is not None and gain_se is not None
                    else None
                ),
                "gain_ci95_high": (
                    (gain_mean + 1.96 * gain_se)
                    if gain_mean is not None and gain_se is not None
                    else None
                ),
            }
        )
    return rows


def run_experiment(mode: str, config_path: str | Path = "config.yaml") -> int:
    root = Path(__file__).resolve().parent
    config_path = Path(config_path)
    if not config_path.is_absolute():
        config_path = (root / config_path).resolve()
    config = load_config(config_path)
    validate_config(config)

    mode = str(mode)
    seeds = (
        [int(seed) for seed in config["seeds"][:3]]
        if mode == "fast"
        else [int(seed) for seed in config["seeds"]]
    )
    if mode == "fast" and len(seeds) != 3:
        raise ValueError("fast mode requires at least three configured seeds")
    save_raw = mode == "fast"

    effective_config = dict(config)
    effective_config.update(
        {"run_mode": mode, "seeds": seeds, "save_raw_trajectories": save_raw}
    )
    config_hash = compute_config_hash(effective_config)
    output_root = resolve_output_dir(root, str(config["output_dir"]), mode)
    dirs = prepare_directories(output_root, save_raw)
    write_yaml(dirs["logs"] / "config_snapshot.yaml", effective_config)

    metadata_path = dirs["logs"] / "run_metadata.json"
    metadata: dict[str, Any] = {
        "experiment_id": config["experiment_id"],
        "mode": mode,
        "config_file": str(config_path.name),
        "config_hash": config_hash,
        "seed_list": seeds,
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "start_time": now_timestamp(),
        "end_time": None,
        "status": "running",
        "backend_status": "running",
        "feedback_timing": "post_decision",
        "state_process": {
            "type": "clipped_ar1",
            "rho": float(config.get("state_rho", 0.98)),
            "sigma": float(config.get("state_sigma", 0.10)),
            "clip": float(config.get("state_clip", 1.0)),
        },
    }
    write_json(metadata_path, metadata)

    try:
        delay_map = {
            setting.name: setting
            for setting in build_delay_settings(switch_t=int(config["T"]) // 2)
        }
        selected_delay_names = [
            DELAY_GROUP_TO_NAME[group] for group in config["delay_settings"]
        ]
        missing_delay_settings = [
            name for name in selected_delay_names if name not in delay_map
        ]
        if missing_delay_settings:
            raise RuntimeError(
                f"Delay builder did not provide expected settings: {missing_delay_settings}"
            )

        write_rows_csv(
            dirs["logs"] / "method_registry.csv",
            METHOD_REGISTRY,
            fieldnames=["method", "method_display_name", "description"],
            append=False,
        )

        run_manifest_rows: list[dict[str, Any]] = []
        seed_summary_rows: list[dict[str, Any]] = []
        trajectory_values: dict[tuple[str, str, int], list[float]] = defaultdict(list)

        T = int(config["T"])
        K = int(config["K"])
        D_max = int(config["D_max"])
        A = list(range(K))
        experiment_id = str(config["experiment_id"])

        for seed in seeds:
            for delay_name in selected_delay_names:
                delay_setting = delay_map[delay_name]
                delay_sequence = build_shared_delay_sequence(T, delay_setting, seed)
                completed_by_method: dict[str, dict[str, Any]] = {}

                for method in config["methods"]:
                    method = str(method)
                    run_id = f"{experiment_id}_{mode}_{config_hash}_{delay_name}_{method}_s{seed:03d}"
                    env = ToyCausalEnv(
                        A=A,
                        seed=seed,
                        rho_state=float(config.get("state_rho", 0.98)),
                        sigma_state=float(config.get("state_sigma", 0.10)),
                        state_clip=float(config.get("state_clip", 1.0)),
                    )
                    learner = learner_for_method(method)
                    started = time.perf_counter()
                    result = run_one_seed(
                        T=T,
                        A=A,
                        D_max=D_max,
                        delay_sampler=delay_setting.sampler,
                        delay_setting_name=delay_name,
                        method_name=method,
                        run_id=run_id,
                        env=env,
                        learner=learner,
                        seed=seed,
                        delay_sequence=delay_sequence,
                    )
                    runtime_seconds = time.perf_counter() - started
                    completed_by_method[method] = result.seed_summary

                    run_manifest_rows.append(
                        {
                            "run_id": run_id,
                            "created_time": now_timestamp(),
                            "experiment_id": experiment_id,
                            "mode": mode,
                            "config_hash": config_hash,
                            "seed": seed,
                            "delay_setting": delay_name,
                            "method": method,
                            "T": T,
                            "K": K,
                            "D_max": D_max,
                            "delay_meta_type": delay_setting.meta.get("type"),
                            "delay_meta_p": delay_setting.meta.get("p"),
                            "delay_meta_w": delay_setting.meta.get("w"),
                            "delay_meta_p_fast": delay_setting.meta.get("p_fast"),
                            "delay_meta_p_slow": delay_setting.meta.get("p_slow"),
                            "delay_meta_switch_t": delay_setting.meta.get("switch_t"),
                        }
                    )

                    for t, regret in enumerate(result.regret, start=1):
                        trajectory_values[(delay_name, method, t)].append(float(regret))

                    if save_raw:
                        write_rows_csv(
                            dirs["raw"] / "delay_schedule.csv",
                            result.delay_rows,
                            RAW_FIELDNAMES["delay_schedule"],
                            append=True,
                        )
                        write_rows_csv(
                            dirs["raw"] / "arrival_log.csv",
                            result.arrival_rows,
                            RAW_FIELDNAMES["arrival_log"],
                            append=True,
                        )
                        write_rows_csv(
                            dirs["raw"] / "step_log.csv",
                            result.step_rows,
                            RAW_FIELDNAMES["step_log"],
                            append=True,
                        )
                        write_rows_csv(
                            dirs["raw"] / "diagnostic_step_log.csv",
                            result.diagnostic_rows,
                            RAW_FIELDNAMES["diagnostic_step_log"],
                            append=True,
                        )

                    summary = result.seed_summary
                    seed_summary_rows.append(
                        {
                            "experiment_id": experiment_id,
                            "mode": mode,
                            "config_hash": config_hash,
                            "run_id": run_id,
                            "seed": seed,
                            "delay_setting": delay_name,
                            "method": method,
                            "T": T,
                            "K": K,
                            "D_max": D_max,
                            "mean_delay": summary["mean_delay"],
                            "median_delay": summary["median_delay"],
                            "p90_delay": summary["p90_delay"],
                            "max_delay": summary["max_delay"],
                            "arrival_rate": summary["arrival_rate_final"],
                            "censor_rate": summary["censor_rate"],
                            "ranking_reversal_rate": summary["ranking_reversal_rate"],
                            "source_state_distance_mean": summary[
                                "source_state_distance_mean"
                            ],
                            "source_state_distance_sum": summary[
                                "source_state_distance_sum"
                            ],
                            "source_state_distance_p90": summary[
                                "source_state_distance_p90"
                            ],
                            "final_Rc": summary["final_causal_regret"],
                            "normalized_final_Rc": summary["normalized_final_regret"],
                            "auc_causal_regret": summary["auc_causal_regret"],
                            "mean_instant_causal_regret": summary[
                                "mean_instant_causal_regret"
                            ],
                            "gain_vs_naive": None,
                            "gain_vs_naive_pct": None,
                            "runtime_seconds": runtime_seconds,
                        }
                    )

                naive_final = float(completed_by_method["naive"]["final_causal_regret"])
                for row in seed_summary_rows[-len(config["methods"]) :]:
                    if row["method"] == "causal_labelled":
                        gain = naive_final - float(row["final_Rc"])
                        row["gain_vs_naive"] = gain
                        row["gain_vs_naive_pct"] = (
                            100.0 * gain / abs(naive_final) if naive_final else 0.0
                        )

        write_rows_csv(
            dirs["logs"] / "run_manifest.csv",
            run_manifest_rows,
            RAW_FIELDNAMES["run_manifest"],
            append=False,
        )
        write_rows_csv(
            dirs["summary"] / "toy_seed_summary.csv",
            seed_summary_rows,
            SEED_SUMMARY_FIELDNAMES,
            append=False,
        )
        write_rows_csv(
            dirs["summary"] / "toy_method_summary.csv",
            _method_summary_rows(seed_summary_rows),
            append=False,
        )
        write_rows_csv(
            dirs["summary"] / "toy_trajectory_summary.csv",
            _trajectory_rows(trajectory_values, experiment_id, mode, config_hash),
            TRAJECTORY_FIELDNAMES,
            append=False,
        )
        generate_figures(output_root)

        metadata.update(
            {
                "status": "success",
                "backend_status": "executed",
                "end_time": now_timestamp(),
            }
        )
        write_json(metadata_path, metadata)
        print(f"Toy {mode} run completed: {output_root}")
        return 0
    except Exception as exc:
        metadata.update(
            {
                "status": "failed",
                "backend_status": "failed",
                "end_time": now_timestamp(),
                "error": repr(exc),
            }
        )
        write_json(metadata_path, metadata)
        raise


def main() -> None:
    args = parse_args()
    raise SystemExit(run_experiment(args.mode, args.config))


if __name__ == "__main__":
    main()

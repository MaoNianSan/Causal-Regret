"""Run Exp4 in isolated directories with seed × condition multiprocessing."""
from __future__ import annotations

import os
for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_thread_env] = "1"

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

import pandas as pd

import config
from engine import run_task


def build_tasks(seeds: list[int], T: int) -> list[dict]:
    tasks: list[dict] = []
    for seed in seeds:
        tasks.append({"kind": "proxy_diagnostic", "seed": seed, "T": T})
        tasks.extend({"kind": "source_label_sweep", "seed": seed, "T": T, "q": q} for q in config.Q_GRID)
        tasks.extend(
            {"kind": "phase_grid", "seed": seed, "T": T, "q": q, "sigma": sigma}
            for q in config.Q_GRID
            for sigma in config.PROXY_SIGMAS
        )
        tasks.extend({"kind": "delay_coupling", "seed": seed, "T": T, "beta": beta} for beta in config.BETA_GRID)
    return tasks


def create_run_dir(mode: str, run_id: str | None) -> Path:
    suffix = run_id or f"{mode}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    path = config.OUTPUT_ROOT / suffix
    if path.exists():
        raise FileExistsError(f"run directory already exists: {path}")
    for name in [
        "raw", "processed", "summaries", "tables", "figures/pdf", "figures/png",
        "figures/data", "figures/metadata", "checks", "logs", "reports", "legacy",
    ]:
        (path / name).mkdir(parents=True, exist_ok=False)
    return path


def run(mode: str, n_jobs: int | None = None, run_id: str | None = None) -> Path:
    seeds, T = config.mode_settings(mode)
    requested_workers = n_jobs or config.auto_workers(mode)
    if requested_workers < 1:
        raise ValueError("n_jobs must be >= 1")
    workers = max(1, min(int(requested_workers), os.cpu_count() or 1, config.auto_workers(mode)))
    run_dir = create_run_dir(mode, run_id)
    tasks = build_tasks(seeds, T)
    rows: list[dict] = []

    print(f"[EXP4] mode={mode}; T={T}; seeds={len(seeds)}; tasks={len(tasks)}; workers={workers}", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run_task, task): task for task in tasks}
        for completed, future in enumerate(as_completed(futures), start=1):
            task = futures[future]
            rows.extend(future.result())
            print(f"[EXP4] completed {completed}/{len(tasks)}: {task['kind']} seed={task['seed']}", flush=True)

    seed_df = pd.DataFrame(rows).sort_values(
        ["subexperiment_id", "seed", "setting_id", "method_id"]
    ).reset_index(drop=True)
    seed_df.to_csv(run_dir / "raw" / "seed_level_results.csv", index=False)
    for subexperiment_id, filename in {
        "proxy_distortion_diagnostic": "proxy_distortion_diagnostic_results.csv",
        "source_label_sweep": "source_label_sweep_results.csv",
        "recoverability_phase_map": "recoverability_phase_map_results.csv",
        "delay_state_coupling_diagnostic": "delay_state_coupling_results.csv",
    }.items():
        seed_df.loc[seed_df["subexperiment_id"].eq(subexperiment_id)].to_csv(run_dir / "raw" / filename, index=False)

    run_config = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "paper_result": False,
        "experiment_id": config.EXPERIMENT_ID,
        "experiment_display_name": config.EXPERIMENT_DISPLAY_NAME,
        "T": T,
        "warmup_t": config.WARMUP_T,
        "primary_metric": "causal_regret_per_round",
        "primary_metric_formula": "mean_{t=warmup_t+1..T}[ell(A_t,S_t)-min_a ell(a,S_t)]",
        "seeds": seeds,
        "n_jobs": workers,
        "requested_n_jobs": requested_workers,
        "task_count": len(tasks),
        "run_directory": str(run_dir),
        "target_mean_delay": config.TARGET_MEAN_DELAY,
        "q_grid": config.Q_GRID,
        "beta_grid": config.BETA_GRID,
        "proxy_sigmas": config.PROXY_SIGMAS,
        "primary_proxy_sigma": config.DEFAULT_PROXY_SIGMA,
        "ci_level": config.CI_LEVEL,
        "n_bootstrap": config.BOOTSTRAP_N,
        "design_note": "fast and full share the complete task grid; only seed count differs",
        "feedback_protocol": "A_u is selected before arrivals at u are processed; anonymous arrival losses are passed to recovery routes without their hidden source index",
        "proxy_interface": "deployable routes receive only simulator-emitted proxy observations at indices no later than the current round",
        "horizon_censoring": "regret is evaluated over all T source actions; post-horizon arrivals cannot update later actions and are shared across methods",
        "interpretation_boundary": "controlled source-label sufficiency and proxy-only recovery limitation stress test; not a logged-data study, online RCT, or information-theoretic impossibility theorem",
        "proxy_route_specification": "proxy_label_recovery uses a fixed bounded-window RBF similarity rule with recency prior over stored observable proxy history; results do not establish optimality or impossibility for all proxy-only algorithms",
    }
    (run_dir / "logs" / "run_config.json").write_text(json.dumps(run_config, indent=2), encoding="utf-8")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["fast", "full"], default="fast")
    parser.add_argument("--n-jobs", type=int, default=None)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    path = run(args.mode, args.n_jobs, args.run_id)
    print(f"RUN_DIR={path}", flush=True)


if __name__ == "__main__":
    main()

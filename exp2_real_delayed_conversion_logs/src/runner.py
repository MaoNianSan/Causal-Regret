from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.common import input_file_identity, validate_exp2_config
from src.parallel import available_cpus, resolve_n_jobs

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config_exp2.yaml"
INPUT_RELATIVE_PATH = Path("inputs") / "pcb_dataset_final.tsv"


def _timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _runtime_config_path(mode: str) -> Path:
    return PROJECT_ROOT / ".runtime" / f"config_exp2_{mode}.yaml"


def _output_root(mode: str) -> Path:
    return PROJECT_ROOT / "outputs" / mode


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _status_path(mode: str) -> Path:
    return _output_root(mode) / "metadata" / "run_status.json"


def _write_status(mode: str, status: str, **extra: Any) -> None:
    expected = int(
        extra.pop("expected_uid_bootstrap_replicates", 200 if mode == "fast" else 1000)
    )
    payload = {
        "experiment_id": "exp2_logged_attribution_sensitivity",
        "mode": mode,
        "status": status,
        "updated_at": _timestamp(),
        "expected_uid_bootstrap_replicates": expected,
        "input_file": str((PROJECT_ROOT / INPUT_RELATIVE_PATH).resolve()),
    }
    payload.update(extra)
    _write_json(_status_path(mode), payload)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Configuration must be a mapping: {path}")
    return payload


def _normalise_n_jobs(value: str | int | None) -> str | int:
    if value is None:
        return "auto"
    if isinstance(value, int):
        if value < 1:
            raise ValueError("--n-jobs must be a positive integer or 'auto'.")
        return value
    text = str(value).strip().lower()
    if text == "auto":
        return "auto"
    result = int(text)
    if result < 1:
        raise ValueError("--n-jobs must be a positive integer or 'auto'.")
    return result


def build_effective_config(
    mode: str,
    base_config: str | Path | None = None,
    n_bootstrap: int | None = None,
    n_jobs: str | int | None = "auto",
    input_path: str | Path | None = None,
) -> Path:
    if mode not in {"fast", "full"}:
        raise ValueError(f"Unsupported mode: {mode}")
    base_path = Path(base_config).resolve() if base_config else DEFAULT_CONFIG
    cfg = copy.deepcopy(_load_yaml(base_path))
    cfg.setdefault("data", {})["raw_file"] = (
        str(Path(input_path)) if input_path else str(INPUT_RELATIVE_PATH)
    )
    validate_exp2_config(cfg)
    bootstrap = cfg.setdefault("statistics", {}).setdefault("uid_bootstrap", {})
    if n_bootstrap is not None:
        if int(n_bootstrap) < 2:
            raise ValueError("--n-bootstrap must be at least 2.")
        bootstrap["n_bootstrap"] = int(n_bootstrap)
    elif mode == "fast":
        bootstrap["n_bootstrap"] = int(bootstrap.get("fast_n_bootstrap", 200))
    else:
        bootstrap["n_bootstrap"] = int(bootstrap.get("n_bootstrap", 1000))

    requested_jobs = _normalise_n_jobs(n_jobs)
    cfg.setdefault("parallel", {})
    cfg.setdefault("runtime", {})["n_jobs"] = requested_jobs
    cfg["runtime"]["host_logical_cpus"] = available_cpus()
    cfg["runtime"]["resolved_bootstrap_workers"] = resolve_n_jobs(
        cfg, int(bootstrap["n_bootstrap"]), purpose="bootstrap"
    )
    cfg["runtime"].update(
        {
            "mode": mode,
            "uid_bootstrap_replicates": int(bootstrap["n_bootstrap"]),
            "generated_by": "src.runner",
            "base_config": str(base_path),
            "project_root": "..",
        }
    )

    root = Path("outputs") / mode
    cfg["outputs"] = {
        "root": str(root),
        "metadata": str(root / "metadata"),
        "precheck": str(root / "precheck"),
        "raw": str(root / "raw"),
        "processed": str(root / "processed"),
        "summaries": str(root / "summaries"),
        "tables": str(root / "tables"),
        "figures": str(root / "figures"),
        "checks": str(root / "checks"),
        "legacy": str(root / "legacy"),
        "self_check": str(root / "checks"),
    }
    runtime_path = _runtime_config_path(mode)
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return runtime_path


def _input_error(input_path: str | Path | None = None) -> str | None:
    path = Path(input_path) if input_path else PROJECT_ROOT / INPUT_RELATIVE_PATH
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        return f"Required local input file is absent: {path}"
    if not path.is_file():
        return f"Configured local input path is not a file: {path}"
    if path.stat().st_size == 0:
        return f"Required local input file is empty: {path}"
    return None


def _resolved_input_file(input_path: str | Path | None = None) -> str:
    path = Path(input_path) if input_path else PROJECT_ROOT / INPUT_RELATIVE_PATH
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path.resolve())


def _child_environment(cfg_path: Path) -> dict[str, str]:
    cfg = _load_yaml(cfg_path)
    blas_threads = int(cfg.get("parallel", {}).get("blas_threads_per_worker", 1))
    env = os.environ.copy()
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        env[name] = str(max(1, blas_threads))
    env["PYTHONHASHSEED"] = "0"
    return env


def _run_step(
    command: list[str],
    step: str,
    mode: str,
    steps: list[dict[str, Any]],
    env: dict[str, str],
    expected_bootstrap: int,
    input_file: str,
) -> int:
    started = _timestamp()
    started_monotonic = time.monotonic()
    print(f"[runner] {step}: {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=PROJECT_ROOT, env=env)
    elapsed_seconds = round(time.monotonic() - started_monotonic, 3)
    print(
        f"[runner] {step}: exit={completed.returncode}; elapsed={elapsed_seconds:.1f}s",
        flush=True,
    )
    steps.append(
        {
            "step": step,
            "command": command,
            "return_code": completed.returncode,
            "started_at": started,
            "finished_at": _timestamp(),
            "elapsed_seconds": elapsed_seconds,
        }
    )
    _write_status(
        mode,
        "running",
        steps=steps,
        expected_uid_bootstrap_replicates=expected_bootstrap,
        input_file=input_file,
    )
    return completed.returncode


def run(
    mode: str,
    base_config: str | Path | None = None,
    n_bootstrap: int | None = None,
    n_jobs: str | int | None = "auto",
    input_path: str | Path | None = None,
) -> int:
    if mode not in {"fast", "full"}:
        return 2
    output_root = _output_root(mode)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    try:
        config_path = build_effective_config(
            mode, base_config, n_bootstrap, n_jobs, input_path
        )
    except Exception as exc:
        _write_status(mode, "blocked_invalid_configuration", error=str(exc), steps=[])
        print(f"[runner] ERROR: {exc}", file=sys.stderr)
        return 2
    input_issue = _input_error(input_path)
    if input_issue:
        expected_bootstrap = int(
            _load_yaml(config_path)["statistics"]["uid_bootstrap"]["n_bootstrap"]
        )
        _write_status(
            mode,
            "blocked_missing_input",
            config_path=str(config_path),
            error=input_issue,
            steps=[],
            expected_uid_bootstrap_replicates=expected_bootstrap,
            input_file=_resolved_input_file(input_path),
        )
        print(f"[runner] ERROR: {input_issue}", file=sys.stderr)
        return 2
    cfg = _load_yaml(config_path)
    validate_exp2_config(cfg)
    expected_bootstrap = int(cfg["statistics"]["uid_bootstrap"]["n_bootstrap"])
    input_file = _resolved_input_file(input_path)
    input_identity = input_file_identity(input_file)
    cfg.setdefault("runtime", {})["input_identity"] = input_identity
    config_path.write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    steps: list[dict[str, Any]] = []
    parallel_meta = {
        "n_jobs": cfg.get("runtime", {}).get("n_jobs"),
        "host_logical_cpus": cfg.get("runtime", {}).get("host_logical_cpus"),
        "resolved_bootstrap_workers": cfg.get("runtime", {}).get(
            "resolved_bootstrap_workers"
        ),
    }
    _write_status(
        mode,
        "running",
        config_path=str(config_path),
        steps=steps,
        started_at=_timestamp(),
        parallel=parallel_meta,
        expected_uid_bootstrap_replicates=expected_bootstrap,
        input_file=input_file,
        input_identity=input_identity,
    )
    executable = sys.executable
    pipeline = [
        ("precheck", [executable, "run_precheck.py", "--config", str(config_path)]),
        (
            "timeline",
            [executable, "construct_timeline.py", "--config", str(config_path)],
        ),
        ("route_assignment", [executable, "run_exp2.py", "--config", str(config_path)]),
        ("statistics", [executable, "stats_exp2.py", "--config", str(config_path)]),
        ("figures", [executable, "plot_exp2.py", "--config", str(config_path)]),
        ("tables", [executable, "make_tables_exp2.py", "--config", str(config_path)]),
        (
            "self_check",
            [
                executable,
                "self_check_exp2.py",
                "--config",
                str(config_path),
                "--mode",
                mode,
                "--allow-running",
            ],
        ),
    ]
    if mode == "full":
        pipeline.append(
            (
                "finalize_paper_result",
                [executable, "finalize_exp2.py", "--config", str(config_path)],
            )
        )
    env = _child_environment(config_path)
    for step, command in pipeline:
        code = _run_step(
            command, step, mode, steps, env, expected_bootstrap, input_file
        )
        if code:
            _write_status(
                mode,
                "failed",
                config_path=str(config_path),
                failed_step=step,
                steps=steps,
                parallel=parallel_meta,
                expected_uid_bootstrap_replicates=expected_bootstrap,
                input_file=input_file,
                input_identity=input_identity,
            )
            print(
                f"[runner] ERROR: step '{step}' failed with exit code {code}.",
                file=sys.stderr,
            )
            return code
    _write_status(
        mode,
        "success",
        config_path=str(config_path),
        steps=steps,
        finished_at=_timestamp(),
        parallel=parallel_meta,
        expected_uid_bootstrap_replicates=expected_bootstrap,
        input_file=input_file,
        input_identity=input_identity,
    )
    print(f"[runner] {mode} completed successfully. Outputs: {output_root}")
    return 0

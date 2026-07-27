"""Low-memory audit of the frozen KuaiRand input split."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, ExperimentConfig
from preprocess_events import required_input_paths
from utilities import day_start_ms, save_json, sha256_file


def _summarize_log(
    path: Path,
    cfg: ExperimentConfig,
    history_start_ms: int,
    boundary_ms: int,
) -> dict[str, Any]:
    header = pd.read_csv(path, nrows=0)
    available = set(header.columns.astype(str))
    required = {cfg.time_col}
    missing = sorted(required - available)
    if missing:
        raise ValueError(f"{path.name} is missing required audit columns: {missing}")
    usecols = [cfg.time_col]
    if "date" in available:
        usecols.append("date")

    row_count = 0
    valid_time_count = 0
    time_min: int | None = None
    time_max: int | None = None
    date_min: int | None = None
    date_max: int | None = None
    date_mismatch_utc = 0
    date_mismatch_shanghai = 0
    comparable_date_rows = 0
    time_before_history_start_count = 0
    time_before_boundary_count = 0
    time_at_or_after_boundary_count = 0
    time_max_before_boundary: int | None = None
    time_min_at_or_after_boundary: int | None = None

    for chunk in pd.read_csv(path, usecols=usecols, chunksize=1_000_000, low_memory=False):
        row_count += len(chunk)
        times = pd.to_numeric(chunk[cfg.time_col], errors="coerce")
        valid = times.notna() & times.gt(0)
        valid_times = times.loc[valid].astype("int64")
        valid_time_count += int(valid.sum())
        if not valid_times.empty:
            chunk_min = int(valid_times.min())
            chunk_max = int(valid_times.max())
            time_min = chunk_min if time_min is None else min(time_min, chunk_min)
            time_max = chunk_max if time_max is None else max(time_max, chunk_max)
            time_before_history_start_count += int(valid_times.lt(history_start_ms).sum())
            before = valid_times.loc[valid_times.lt(boundary_ms)]
            at_or_after = valid_times.loc[valid_times.ge(boundary_ms)]
            time_before_boundary_count += len(before)
            time_at_or_after_boundary_count += len(at_or_after)
            if not before.empty:
                chunk_max_before = int(before.max())
                time_max_before_boundary = (
                    chunk_max_before
                    if time_max_before_boundary is None
                    else max(time_max_before_boundary, chunk_max_before)
                )
            if not at_or_after.empty:
                chunk_min_after = int(at_or_after.min())
                time_min_at_or_after_boundary = (
                    chunk_min_after
                    if time_min_at_or_after_boundary is None
                    else min(time_min_at_or_after_boundary, chunk_min_after)
                )

        if "date" in chunk.columns:
            dates = pd.to_numeric(chunk["date"], errors="coerce")
            valid_date = valid & dates.notna()
            comparable_date_rows += int(valid_date.sum())
            if valid_date.any():
                date_values = dates.loc[valid_date].astype("int64")
                chunk_date_min = int(date_values.min())
                chunk_date_max = int(date_values.max())
                date_min = chunk_date_min if date_min is None else min(date_min, chunk_date_min)
                date_max = chunk_date_max if date_max is None else max(date_max, chunk_date_max)
                unique_dates = date_values.unique().tolist()
                date_text = {
                    value: pd.to_datetime(str(value), format="%Y%m%d").strftime("%Y-%m-%d")
                    for value in unique_dates
                }
                utc_starts = date_values.map(
                    {value: day_start_ms(date_text[value], "UTC") for value in unique_dates}
                ).to_numpy(np.int64)
                shanghai_starts = date_values.map(
                    {
                        value: day_start_ms(date_text[value], "Asia/Shanghai")
                        for value in unique_dates
                    }
                ).to_numpy(np.int64)
                comparable_times = times.loc[valid_date].astype("int64").to_numpy()
                date_mismatch_utc += int(
                    ((comparable_times < utc_starts) | (comparable_times >= utc_starts + 86_400_000)).sum()
                )
                date_mismatch_shanghai += int(
                    (
                        (comparable_times < shanghai_starts)
                        | (comparable_times >= shanghai_starts + 86_400_000)
                    ).sum()
                )

    return {
        "file_name": path.name,
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "row_count": row_count,
        "valid_time_count": valid_time_count,
        "time_min_ms": time_min,
        "time_max_ms": time_max,
        "time_min_utc": None if time_min is None else pd.to_datetime(time_min, unit="ms", utc=True).isoformat(),
        "time_max_utc": None if time_max is None else pd.to_datetime(time_max, unit="ms", utc=True).isoformat(),
        "date_min": date_min,
        "date_max": date_max,
        "comparable_date_rows": comparable_date_rows,
        "date_mismatch_rate_utc": None if comparable_date_rows == 0 else date_mismatch_utc / comparable_date_rows,
        "date_mismatch_rate_asia_shanghai": None if comparable_date_rows == 0 else date_mismatch_shanghai / comparable_date_rows,
        "time_before_history_start_count": time_before_history_start_count,
        "time_before_boundary_count": time_before_boundary_count,
        "time_at_or_after_boundary_count": time_at_or_after_boundary_count,
        "time_max_before_boundary_ms": time_max_before_boundary,
        "time_min_at_or_after_boundary_ms": time_min_at_or_after_boundary,
    }


def audit_inputs(
    project_root: Path,
    *,
    input_root: Path | None = None,
    output_dir: Path | None = None,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    input_root = (input_root or (project_root / "inputs" / "KuaiRand-1K")).resolve()
    output_dir = (output_dir or (project_root / "outputs" / "input_audit")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = required_input_paths(input_root, cfg)
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing frozen KuaiRand inputs: " + ", ".join(str(path) for path in missing))

    history_start_ms = day_start_ms(cfg.history_start_local_date, cfg.timezone_name)
    boundary_ms = day_start_ms(cfg.split_boundary_local_date, cfg.timezone_name)
    history = _summarize_log(paths[0], cfg, history_start_ms, boundary_ms)
    evaluation = _summarize_log(paths[1], cfg, history_start_ms, boundary_ms)
    video = {
        "file_name": paths[2].name,
        "path": str(paths[2].resolve()),
        "size_bytes": paths[2].stat().st_size,
        "sha256": sha256_file(paths[2]),
    }
    history_max = history["time_max_ms"]
    evaluation_min = evaluation["time_min_ms"]
    raw_strict_nonoverlap = (
        history_max is not None
        and evaluation_min is not None
        and int(history_max) < int(evaluation_min)
    )
    history_prestart_count = int(history["time_before_history_start_count"])
    history_prestart_fraction = (
        history_prestart_count / int(history["valid_time_count"])
        if int(history["valid_time_count"])
        else 0.0
    )
    history_crossing_count = int(history["time_at_or_after_boundary_count"])
    evaluation_preboundary_count = int(evaluation["time_before_boundary_count"])
    evaluation_preboundary_fraction = (
        evaluation_preboundary_count / int(evaluation["valid_time_count"])
        if int(evaluation["valid_time_count"])
        else 0.0
    )
    retained_evaluation_min = evaluation["time_min_at_or_after_boundary_ms"]
    retained_strict_nonoverlap = (
        history_max is not None
        and retained_evaluation_min is not None
        and int(history_max) < int(retained_evaluation_min)
    )
    boundary_policy_pass = (
        history_prestart_fraction <= cfg.max_prestart_history_fraction
        and history_crossing_count == 0
        and evaluation_preboundary_fraction <= cfg.max_preboundary_evaluation_fraction
        and retained_strict_nonoverlap
    )
    payload = {
        "audit_status": "PASS" if boundary_policy_pass else "STOP_AND_REVIEW",
        "input_quality_status": (
            "PASS_WITH_BOUNDARY_QUARANTINE"
            if boundary_policy_pass
            and (history_prestart_count > 0 or evaluation_preboundary_count > 0)
            else ("PASS" if boundary_policy_pass else "STOP_AND_REVIEW")
        ),
        "input_root": str(input_root),
        "history": history,
        "evaluation": evaluation,
        "video": video,
        "history_and_evaluation_same_sha256": history["sha256"] == evaluation["sha256"],
        "timezone_name": cfg.timezone_name,
        "timezone_rule": cfg.timezone_rule,
        "history_start_local_date": cfg.history_start_local_date,
        "history_start_time_ms": history_start_ms,
        "split_boundary_local_date": cfg.split_boundary_local_date,
        "split_boundary_time_ms": boundary_ms,
        "boundary_policy": "quarantine_events_outside_frozen_split_boundaries",
        "history_events_before_start": history_prestart_count,
        "history_prestart_fraction": history_prestart_fraction,
        "max_prestart_history_fraction": cfg.max_prestart_history_fraction,
        "history_events_at_or_after_boundary": history_crossing_count,
        "evaluation_events_before_boundary": evaluation_preboundary_count,
        "evaluation_preboundary_fraction": evaluation_preboundary_fraction,
        "max_preboundary_evaluation_fraction": cfg.max_preboundary_evaluation_fraction,
        "raw_strict_event_time_nonoverlap": raw_strict_nonoverlap,
        "retained_strict_event_time_nonoverlap": retained_strict_nonoverlap,
        "raw_overlap_width_ms": (
            None
            if history_max is None or evaluation_min is None
            else max(0, int(history_max) - int(evaluation_min))
        ),
    }
    save_json(payload, output_dir / "exp3_input_split_audit.json")

    print()
    print("EXP3 INPUT AUDIT")
    print("-" * 68)
    print(f"Status                     {payload['audit_status']}")
    print(f"Input root                 {input_root}")
    print(f"History rows               {history['row_count']}")
    print(f"History time range         {history['time_min_utc']} -> {history['time_max_utc']}")
    print(f"Evaluation rows            {evaluation['row_count']}")
    print(f"Evaluation time range      {evaluation['time_min_utc']} -> {evaluation['time_max_utc']}")
    print(f"Input quality              {payload['input_quality_status']}")
    print(f"History start              {cfg.history_start_local_date} 00:00 {cfg.timezone_name}")
    print(f"Frozen boundary            {cfg.split_boundary_local_date} 00:00 {cfg.timezone_name}")
    print(f"Pre-start history rows     {history_prestart_count} ({history_prestart_fraction:.6%})")
    print(f"Pre-boundary eval rows     {evaluation_preboundary_count} ({evaluation_preboundary_fraction:.6%})")
    print(f"Raw event nonoverlap       {raw_strict_nonoverlap}")
    print(f"Retained event nonoverlap  {retained_strict_nonoverlap}")
    print(f"Same file hash             {payload['history_and_evaluation_same_sha256']}")
    print(f"Audit report               {output_dir / 'exp3_input_split_audit.json'}")
    print("-" * 68)
    return payload

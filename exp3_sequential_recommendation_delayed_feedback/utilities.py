"""Shared deterministic utilities for Experiment 3."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

EPS = 1e-12
_RUN_METADATA: dict[str, Any] = {}


def set_run_metadata(metadata: dict[str, Any]) -> None:
    """Set row-level provenance stamped on paper-facing tabular artifacts."""
    _RUN_METADATA.clear()
    _RUN_METADATA.update(metadata)



def stable_uint64(value: object, salt: str) -> int:
    payload = f"{salt}::{value}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=False)


def stable_group(value: object, group_count: int, salt: str) -> int:
    if group_count <= 0:
        raise ValueError("group_count must be positive")
    return stable_uint64(value, salt) % group_count


def stable_uniform(value: object, salt: str) -> float:
    return stable_uint64(value, salt) / float(2**64 - 1)


def parse_primary_tag(value: object) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return ""
    for separator in (",", "|", ";", " "):
        if separator in text:
            text = text.split(separator, 1)[0].strip()
    return text


def coerce_binary(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0.0)
    return values.gt(0).astype(np.int8)


def coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def require_columns(frame: pd.DataFrame, columns: Iterable[str], label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def calendar_day(
    time_ms: pd.Series | np.ndarray,
    timezone_name: str,
) -> pd.Series:
    values = pd.Series(np.asarray(time_ms, dtype=np.int64))
    return (
        pd.to_datetime(values, unit="ms", utc=True)
        .dt.tz_convert(timezone_name)
        .dt.strftime("%Y-%m-%d")
    )


def utc_calendar_day(time_ms: pd.Series | np.ndarray) -> pd.Series:
    """Backward-compatible UTC day conversion for callers outside Exp3."""
    return calendar_day(time_ms, "UTC")


def day_start_ms(calendar_day: str, timezone_name: str = "UTC") -> int:
    return int(pd.Timestamp(calendar_day, tz=timezone_name).timestamp() * 1000)


def next_day_start_ms(calendar_day: str, timezone_name: str = "UTC") -> int:
    return int(
        (pd.Timestamp(calendar_day, tz=timezone_name) + pd.Timedelta(days=1)).timestamp()
        * 1000
    )


def save_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.ndarray,)):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def save_frame(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = frame.copy()
    # Internal high-volume processed event tables use manifest/sidecar provenance.
    # Paper-facing design, derived, and table artifacts carry row-level metadata.
    should_stamp = bool({"design", "derived", "tables"}.intersection(path.parts))
    if should_stamp and _RUN_METADATA:
        for key, value in _RUN_METADATA.items():
            if key not in output.columns:
                output[key] = value
    if path.suffix.lower() == ".parquet":
        try:
            output.to_parquet(path, index=False)
            return path
        except Exception:
            fallback = path.with_suffix(".csv")
            output.to_csv(fallback, index=False)
            return fallback
    output.to_csv(path, index=False)
    return path


def read_frame(path: Path) -> pd.DataFrame:
    if path.exists():
        if path.suffix.lower() == ".parquet":
            try:
                return pd.read_parquet(path)
            except (ImportError, ValueError, OSError):
                fallback = path.with_suffix(".csv")
                if fallback.exists():
                    return pd.read_csv(fallback)
                raise
        return pd.read_csv(path)
    alternate = path.with_suffix(".csv") if path.suffix.lower() == ".parquet" else path.with_suffix(".parquet")
    if alternate.exists():
        return read_frame(alternate)
    raise FileNotFoundError(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_required(relative_path: str) -> bool:
    if relative_path.startswith("processed/"):
        return False
    return relative_path != "derived/exp3_evaluation_arrays.npz"


def build_artifact_manifest(output_dir: Path) -> pd.DataFrame:
    manifest_path = output_dir / "metadata" / "run_manifest.json"
    run_manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {}
    )
    rows: list[dict[str, Any]] = []
    for path in sorted(p for p in output_dir.rglob("*") if p.is_file()):
        if path.name in {"artifacts_manifest.csv", "artifact_manifest.csv"}:
            continue
        relative = path.relative_to(output_dir).as_posix()
        rows.append(
            {
                "relative_path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "archive_required": _archive_required(relative),
                "code_version_type": run_manifest.get("code_version_type", "unknown"),
                "code_version": run_manifest.get("code_version", "unknown"),
            }
        )
    manifest = pd.DataFrame(rows)
    targets = (
        output_dir / "metadata" / "artifacts_manifest.csv",
        output_dir / "manifest" / "artifact_manifest.csv",
    )
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        manifest.to_csv(target, index=False)
    return manifest


def percentile_interval(values: np.ndarray, ci_level: float) -> tuple[float, float]:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return np.nan, np.nan
    alpha = 1.0 - ci_level
    return (
        float(np.quantile(finite, alpha / 2.0)),
        float(np.quantile(finite, 1.0 - alpha / 2.0)),
    )


def spearman_correlation(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 3:
        return np.nan
    xr = pd.Series(x[mask]).rank(method="average").to_numpy(float)
    yr = pd.Series(y[mask]).rank(method="average").to_numpy(float)
    if np.std(xr) <= EPS or np.std(yr) <= EPS:
        return np.nan
    return float(np.corrcoef(xr, yr)[0, 1])


def deterministic_tie_argmax(values: np.ndarray, action_order: np.ndarray) -> int:
    values = np.asarray(values, dtype=float)
    action_order = np.asarray(action_order, dtype=int)
    finite = np.isfinite(values)
    if not finite.any():
        raise ValueError("Cannot select an action from all-NA values")
    best = np.nanmax(values)
    candidates = action_order[np.isclose(values[action_order], best, rtol=0.0, atol=1e-12)]
    if candidates.size == 0:
        candidates = action_order[np.nanargmax(values[action_order]) : np.nanargmax(values[action_order]) + 1]
    return int(candidates[0])

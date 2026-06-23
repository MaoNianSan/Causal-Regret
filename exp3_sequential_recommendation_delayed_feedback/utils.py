from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

EPS = 1e-8


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def stable_json_hash(payload: Any) -> str:
    """Return a deterministic SHA-256 hash for JSON-serializable content."""
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_csv_checked(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return pd.read_csv(path, **kwargs)


def require_columns(df: pd.DataFrame, required: Sequence[str], name: str) -> None:
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in {name}: {missing}")


def coerce_binary(series: pd.Series) -> pd.Series:
    return (pd.to_numeric(series, errors="coerce").fillna(0) > 0).astype(np.int8)


def coerce_numeric(series: pd.Series, fill: float = 0.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(fill)


def parse_primary_tag(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "unknown"
    text = str(value).strip().strip("[](){}\"'")
    if not text or text.lower() in {"nan", "none", "null"}:
        return "unknown"
    parts = [part for part in re.split(r"[,;|/\\\s]+", text) if part]
    return parts[0] if parts else "unknown"


def save_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def maybe_save_parquet(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(path, index=False)
        return path
    except Exception:
        fallback = path.with_suffix(".csv")
        df.to_csv(fallback, index=False)
        return fallback


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_artifact_manifest(output_dir: Path) -> pd.DataFrame:
    """Inventory generated artifacts after the run metadata is finalized."""
    rows: list[dict[str, Any]] = []
    manifest_path = output_dir / "metadata" / "artifacts_manifest.csv"
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path != manifest_path:
            rows.append({
                "relative_path": str(path.relative_to(output_dir)).replace("\\", "/"),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    return pd.DataFrame(rows)


def write_artifact_manifest(output_dir: Path) -> None:
    save_dataframe(build_artifact_manifest(output_dir), output_dir / "metadata" / "artifacts_manifest.csv")


def stable_uint64(series: pd.Series) -> np.ndarray:
    return pd.util.hash_pandas_object(series.astype(str), index=False).to_numpy(dtype=np.uint64)


def splitmix64_uniform(keys: np.ndarray, seed: int) -> np.ndarray:
    """Deterministic U[0, 1) values from uint64 keys and a mask seed."""
    with np.errstate(over="ignore"):
        z = np.asarray(keys, dtype=np.uint64) + np.uint64(0x9E3779B97F4A7C15) * np.uint64(seed + 1)
    z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    z = z ^ (z >> np.uint64(31))
    return ((z >> np.uint64(11)).astype(np.float64)) * (1.0 / float(1 << 53))


def percentile_ci(values: Sequence[float], level: float = 0.95) -> tuple[float, float]:
    values_array = np.asarray(values, dtype=float)
    values_array = values_array[np.isfinite(values_array)]
    if values_array.size == 0:
        return (np.nan, np.nan)
    alpha = (1.0 - level) / 2.0
    return (float(np.quantile(values_array, alpha)), float(np.quantile(values_array, 1.0 - alpha)))

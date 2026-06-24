"""Small, deterministic IO and numeric utilities for Exp3."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

EPS = 1e-8


def utf8_safe_text(value: Any) -> str:
    """Return a display-safe UTF-8 string even when a path contains surrogates.

    Zip archives created on a different platform can occasionally be extracted
    into a directory whose decoded name contains surrogate code points.  Python
    can still access those paths, but a direct UTF-8 CSV/JSON write then fails.
    This helper preserves ordinary Unicode and escapes only unencodable units.
    """
    return str(value).encode("utf-8", errors="backslashreplace").decode("utf-8")


def logical_path(path: Path, root: Path | None = None) -> str:
    """Return a portable, UTF-8-safe path representation for metadata outputs."""
    try:
        rendered = (
            path.relative_to(root).as_posix() if root is not None else path.as_posix()
        )
    except ValueError:
        rendered = path.name
    return utf8_safe_text(rendered)


def _atomic_replace(temp_path: Path, target_path: Path) -> None:
    """Atomically replace ``target_path`` with a completed temporary artifact."""
    os.replace(temp_path, target_path)


def _temporary_path(target_path: Path, suffix: str) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="wb",
        prefix=f".{target_path.name}.",
        suffix=suffix,
        dir=target_path.parent,
        delete=False,
    )
    handle.close()
    return Path(handle.name)


def _sanitize_dataframe_for_utf8(df: pd.DataFrame) -> pd.DataFrame:
    """Escape only string/object cells that cannot be encoded as UTF-8."""
    out = df.copy()
    for column in out.columns:
        if pd.api.types.is_object_dtype(out[column]) or pd.api.types.is_string_dtype(
            out[column]
        ):
            out[column] = out[column].map(
                lambda value: (
                    utf8_safe_text(value) if isinstance(value, (str, Path)) else value
                )
            )
    return out


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically with path-safe UTF-8 content."""
    rendered = utf8_safe_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    )
    temporary = _temporary_path(path, ".json.tmp")
    try:
        temporary.write_text(rendered, encoding="utf-8")
        _atomic_replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def stable_json_hash(payload: Any) -> str:
    """Return a deterministic SHA-256 hash for JSON-serializable content."""
    encoded = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, default=str, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_csv_checked(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {logical_path(path)}")
    return pd.read_csv(path, **kwargs)


def require_columns(df: pd.DataFrame, required: Sequence[str], name: str) -> None:
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns in {utf8_safe_text(name)}: {missing}"
        )


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
    """Write a CSV atomically and avoid failures from malformed path text."""
    temporary = _temporary_path(path, ".csv.tmp")
    try:
        _sanitize_dataframe_for_utf8(df).to_csv(
            temporary, index=False, encoding="utf-8", errors="backslashreplace"
        )
        _atomic_replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def maybe_save_parquet(df: pd.DataFrame, path: Path) -> Path:
    """Write parquet atomically; fall back to an atomic CSV when unavailable."""
    temporary = _temporary_path(path, ".parquet")
    try:
        try:
            _sanitize_dataframe_for_utf8(df).to_parquet(temporary, index=False)
            _atomic_replace(temporary, path)
            return path
        except Exception:
            temporary.unlink(missing_ok=True)
            fallback = path.with_suffix(".csv")
            save_dataframe(df, fallback)
            return fallback
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_artifact_manifest(output_dir: Path) -> pd.DataFrame:
    """Inventory generated artifacts after run metadata is finalized."""
    rows: list[dict[str, Any]] = []
    manifest_path = output_dir / "metadata" / "artifacts_manifest.csv"
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path != manifest_path:
            rows.append(
                {
                    "relative_path": logical_path(path, output_dir),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return pd.DataFrame(rows)


def write_artifact_manifest(output_dir: Path) -> None:
    save_dataframe(
        build_artifact_manifest(output_dir),
        output_dir / "metadata" / "artifacts_manifest.csv",
    )


def stable_uint64(series: pd.Series) -> np.ndarray:
    return pd.util.hash_pandas_object(series.astype(str), index=False).to_numpy(
        dtype=np.uint64
    )


def splitmix64_uniform(keys: np.ndarray, seed: int) -> np.ndarray:
    """Deterministic U[0, 1) values from uint64 keys and a mask seed."""
    with np.errstate(over="ignore"):
        z = np.asarray(keys, dtype=np.uint64) + np.uint64(
            0x9E3779B97F4A7C15
        ) * np.uint64(seed + 1)
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
    return (
        float(np.quantile(values_array, alpha)),
        float(np.quantile(values_array, 1.0 - alpha)),
    )

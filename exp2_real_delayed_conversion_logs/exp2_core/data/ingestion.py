from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from tqdm.auto import tqdm

from contracts import (
    ConfigurationError,
    DataContractError,
    REQUIRED_RAW_LOGICAL_COLUMNS,
    require_columns,
)

from .temporal_filters import (
    make_decision_cell_id,
    normalize_identifier,
    normalize_user_identifier,
    to_numeric,
    to_timestamp_utc,
)


INPUT_SCHEMA_VERSION = "exp2_delayed_conversion_log_v1"


@dataclass(frozen=True)
class RawScanResult:
    candidate_chunks: list[pd.DataFrame]
    impression_aggregates: list[pd.DataFrame]
    observed_start: pd.Timestamp
    observed_end: pd.Timestamp
    raw_row_count: int
    sampled_row_count: int
    invalid_timestamp_count: int
    conversion_candidate_count_before_timing: int
    input_manifest: dict[str, Any]
    candidate_window_days: float


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigurationError(f"Configuration file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ConfigurationError("Configuration root must be a mapping.")
    required_sections = {
        "experiment",
        "input",
        "cohort",
        "decision_cell",
        "routes",
        "ranking",
        "resampling",
        "runtime",
        "storage",
        "plots",
    }
    missing = sorted(required_sections.difference(config))
    if missing:
        raise ConfigurationError(f"Missing configuration sections: {missing}")
    column_map = config["input"].get("columns", {})
    missing_logical = [name for name in REQUIRED_RAW_LOGICAL_COLUMNS if name not in column_map]
    if missing_logical:
        raise ConfigurationError(f"Missing logical input-column mappings: {missing_logical}")
    if str(config["experiment"].get("schema_version", "")) != "exp2_attribution_sensitivity_v2":
        raise ConfigurationError("Exp2 configuration must declare schema_version=exp2_attribution_sensitivity_v2.")
    if float(config["cohort"].get("primary_candidate_window_days", 0)) != 7.0:
        raise ConfigurationError("Primary candidate window is frozen at 7 days.")
    if int(config["decision_cell"].get("minimum_impressions", 0)) != 50:
        raise ConfigurationError("Minimum impression support is frozen at 50.")
    return config


def canonical_json_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: str | Path, *, block_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            block = handle.read(block_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def build_input_manifest(path: str | Path) -> dict[str, Any]:
    input_path = Path(path).resolve()
    if not input_path.exists():
        raise DataContractError(f"Input file not found: {input_path}")
    stat = input_path.stat()
    content_sha256 = file_sha256(input_path)
    content_identity = {
        "input_schema_version": INPUT_SCHEMA_VERSION,
        "input_size_bytes": int(stat.st_size),
        "input_content_sha256": content_sha256,
    }
    return {
        "input_basename": input_path.name,
        "input_location": str(input_path),
        "input_size_bytes": int(stat.st_size),
        "input_modified_time_ns": int(stat.st_mtime_ns),
        "input_content_sha256": content_sha256,
        "input_schema_version": INPUT_SCHEMA_VERSION,
        "content_identity": content_identity,
    }


def input_manifest_identity_hash(manifest: dict[str, Any]) -> str:
    identity = manifest.get("content_identity")
    if not isinstance(identity, dict):
        raise DataContractError("Input manifest is missing a stable content_identity mapping.")
    return canonical_json_hash(identity)


def _fast_user_mask(users: pd.Series, *, numerator: int, denominator: int) -> pd.Series:
    if denominator <= 0 or numerator <= 0 or numerator > denominator:
        raise ConfigurationError("Invalid deterministic fast-sampling fraction.")
    hashes = pd.util.hash_pandas_object(users.astype("string"), index=False, categorize=True)
    return hashes.mod(denominator).lt(numerator)


def _resolve_usecols(column_map: dict[str, str]) -> list[str]:
    return sorted(set(column_map.values()))


def scan_raw_log(
    input_path: str | Path,
    config: dict[str, Any],
    *,
    mode: str,
    progress: bool,
    apply_fast_hash_sample: bool | None,
) -> RawScanResult:
    input_path = Path(input_path)
    column_map = config["input"]["columns"]
    separator = str(config["input"].get("separator", "\t"))
    timestamp_unit = str(config["input"].get("timestamp_unit", "seconds"))
    if timestamp_unit == "seconds":
        timestamp_unit = "s"
    chunk_size = int(config["input"].get("chunk_size", 500_000))
    candidate_window_days = max(
        [
            float(config["cohort"].get("primary_candidate_window_days", 7.0)),
            *[float(value) for value in config["cohort"].get("robustness_candidate_window_days", [])],
        ]
    )
    if apply_fast_hash_sample is None:
        apply_fast_hash_sample = mode == "fast" and not bool(config.get("fast", {}).get("synthetic_fixture", False))
    manifest = build_input_manifest(input_path)
    usecols = _resolve_usecols(column_map)
    candidate_chunks: list[pd.DataFrame] = []
    impression_aggregates: list[pd.DataFrame] = []
    observed_start: pd.Timestamp | None = None
    observed_end: pd.Timestamp | None = None
    raw_row_offset = 0
    raw_row_count = 0
    sampled_row_count = 0
    invalid_timestamp_count = 0
    conversion_candidate_count_before_timing = 0
    reader = pd.read_csv(
        input_path,
        sep=separator,
        usecols=lambda name: name in usecols,
        chunksize=chunk_size,
        low_memory=False,
    )
    iterator = tqdm(reader, desc="Scan delayed-conversion log", disable=not progress, unit="chunk")
    for chunk in iterator:
        raw_row_count += len(chunk)
        rename_map = {raw_name: logical for logical, raw_name in column_map.items() if raw_name in chunk}
        chunk = chunk.rename(columns=rename_map)
        require_columns(chunk.columns, REQUIRED_RAW_LOGICAL_COLUMNS, context="raw log chunk")
        chunk["raw_row_id"] = np.arange(raw_row_offset, raw_row_offset + len(chunk), dtype=np.int64)
        raw_row_offset += len(chunk)
        chunk["user_id"] = normalize_user_identifier(chunk["uid"])
        chunk["campaign_id"] = normalize_identifier(chunk["campaign"])
        chunk["conversion_id"] = normalize_identifier(chunk["conversion_id"])
        if mode == "fast" and apply_fast_hash_sample:
            fast_cfg = config.get("fast", {})
            mask = _fast_user_mask(
                chunk["user_id"],
                numerator=int(fast_cfg.get("real_data_user_hash_numerator", 1)),
                denominator=int(fast_cfg.get("real_data_user_hash_denominator", 100)),
            )
            chunk = chunk.loc[mask].copy()
        sampled_row_count += len(chunk)
        if chunk.empty:
            continue
        chunk["event_timestamp_utc"] = to_timestamp_utc(chunk["timestamp"], timestamp_unit)
        chunk["conversion_timestamp_utc"] = to_timestamp_utc(chunk["conversion_timestamp"], timestamp_unit)
        invalid_timestamp_count += int(chunk["event_timestamp_utc"].isna().sum())
        valid_event_times = chunk["event_timestamp_utc"].dropna()
        if not valid_event_times.empty:
            chunk_min = valid_event_times.min()
            chunk_max = valid_event_times.max()
            observed_start = chunk_min if observed_start is None else min(observed_start, chunk_min)
            observed_end = chunk_max if observed_end is None else max(observed_end, chunk_max)
        impression_rows = chunk[
            chunk["campaign_id"].notna() & chunk["event_timestamp_utc"].notna()
        ].copy()
        if not impression_rows.empty:
            impression_rows["source_date_utc"] = impression_rows["event_timestamp_utc"].dt.floor("D")
            impression_rows["decision_cell_id"] = make_decision_cell_id(
                impression_rows["campaign_id"], impression_rows["source_date_utc"]
            )
            aggregate = (
                impression_rows.groupby(
                    ["decision_cell_id", "campaign_id", "source_date_utc"],
                    sort=False,
                    observed=True,
                )
                .size()
                .rename("eligible_impression_count")
                .reset_index()
            )
            impression_aggregates.append(aggregate)
        conversion_flag = to_numeric(chunk["conversion"]).eq(1)
        conversion_candidate_count_before_timing += int(conversion_flag.sum())
        event_numeric = chunk["event_timestamp_utc"]
        conversion_numeric = chunk["conversion_timestamp_utc"]
        lag_days = (conversion_numeric - event_numeric).dt.total_seconds() / 86_400.0
        candidate_mask = (
            conversion_flag
            & chunk["conversion_id"].notna()
            & chunk["user_id"].notna()
            & chunk["campaign_id"].notna()
            & event_numeric.notna()
            & conversion_numeric.notna()
            & lag_days.ge(0.0)
            & lag_days.le(candidate_window_days)
        )
        candidates = chunk.loc[candidate_mask].copy()
        if candidates.empty:
            continue
        candidates["source_lag_days"] = lag_days.loc[candidate_mask].astype(float)
        candidates["source_date_utc"] = candidates["event_timestamp_utc"].dt.floor("D")
        candidates["arrival_date_utc"] = candidates["conversion_timestamp_utc"].dt.floor("D")
        candidates["decision_cell_id"] = make_decision_cell_id(candidates["campaign_id"], candidates["source_date_utc"])
        candidates["arrival_anchor_cell_id"] = make_decision_cell_id(candidates["campaign_id"], candidates["arrival_date_utc"])
        candidates["is_click"] = to_numeric(candidates["click"]).fillna(0).eq(1)
        candidates["is_logged_attributed"] = to_numeric(candidates["attribution"]).fillna(0).eq(1)
        candidate_chunks.append(
            candidates[
                [
                    "raw_row_id", "user_id", "conversion_id", "campaign_id",
                    "event_timestamp_utc", "conversion_timestamp_utc", "source_date_utc",
                    "arrival_date_utc", "decision_cell_id", "arrival_anchor_cell_id",
                    "source_lag_days", "is_click", "is_logged_attributed",
                ]
            ].copy()
        )
    if observed_start is None or observed_end is None:
        raise DataContractError("No valid event timestamps were observed in the input log.")
    if not candidate_chunks:
        raise DataContractError("No valid delayed-conversion candidate rows were constructed.")
    if not impression_aggregates:
        raise DataContractError("No decision-cell impression counts were constructed.")
    return RawScanResult(
        candidate_chunks=candidate_chunks,
        impression_aggregates=impression_aggregates,
        observed_start=observed_start,
        observed_end=observed_end,
        raw_row_count=raw_row_count,
        sampled_row_count=sampled_row_count,
        invalid_timestamp_count=invalid_timestamp_count,
        conversion_candidate_count_before_timing=conversion_candidate_count_before_timing,
        input_manifest=manifest,
        candidate_window_days=candidate_window_days,
    )

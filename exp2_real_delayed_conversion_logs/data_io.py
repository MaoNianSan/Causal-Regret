from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

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


@dataclass(frozen=True)
class PreparedRawData:
    candidates: pd.DataFrame
    impression_counts: pd.DataFrame
    observed_start_utc: pd.Timestamp
    observed_end_utc: pd.Timestamp
    audit: dict[str, Any]
    input_manifest: dict[str, Any]


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
        "statistics",
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


INPUT_SCHEMA_VERSION = "exp2_delayed_conversion_log_v1"


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


def normalize_identifier(series: pd.Series) -> pd.Series:
    values = series.astype("string").str.strip()
    invalid = values.isna() | values.eq("") | values.str.lower().isin({"nan", "none", "null"})
    return values.mask(invalid)


def normalize_user_identifier(series: pd.Series) -> pd.Series:
    values = normalize_identifier(series)
    invalid = values.isin({"-1", "-1.0"})
    return values.mask(invalid)


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _to_timestamp_utc(series: pd.Series, unit: str) -> pd.Series:
    numeric = _to_numeric(series)
    return pd.to_datetime(numeric, unit=unit, utc=True, errors="coerce")


def make_decision_cell_id(campaign_id: pd.Series, date_utc: pd.Series) -> pd.Series:
    campaign = normalize_identifier(campaign_id)
    date_text = pd.to_datetime(date_utc, utc=True, errors="coerce").dt.strftime("%Y-%m-%d")
    return campaign.astype("string") + "|" + date_text.astype("string")


def _stable_hash_strings(frame: pd.DataFrame, columns: Iterable[str]) -> pd.Series:
    require_columns(frame.columns, columns, context="stable hash")
    hashes = pd.util.hash_pandas_object(frame[list(columns)], index=False, categorize=True)
    return hashes.map(lambda value: f"{int(value):016x}").astype("string")


def _fast_user_mask(users: pd.Series, *, numerator: int, denominator: int) -> pd.Series:
    if denominator <= 0 or numerator <= 0 or numerator > denominator:
        raise ConfigurationError("Invalid deterministic fast-sampling fraction.")
    hashes = pd.util.hash_pandas_object(users.astype("string"), index=False, categorize=True)
    return hashes.mod(denominator).lt(numerator)


def _resolve_usecols(column_map: dict[str, str]) -> list[str]:
    return sorted(set(column_map.values()))


def prepare_raw_log(
    input_path: str | Path,
    config: dict[str, Any],
    *,
    mode: str,
    progress: bool = True,
    apply_fast_hash_sample: bool | None = None,
) -> PreparedRawData:
    """Read the Criteo log once, stage conversion candidates, and aggregate cell exposure.

    The scan is route-independent. Full mode uses every input row. Fast mode applies a
    deterministic user-hash sample before constructing the smoke-test cohort.
    """

    input_path = Path(input_path)
    column_map = config["input"]["columns"]
    separator = str(config["input"].get("separator", "\t"))
    timestamp_unit = str(config["input"].get("timestamp_unit", "seconds"))
    if timestamp_unit == "seconds":
        timestamp_unit = "s"
    chunk_size = int(config["input"].get("chunk_size", 500_000))
    candidate_window_days = float(config["cohort"]["candidate_window_days"])
    if apply_fast_hash_sample is None:
        apply_fast_hash_sample = (
            mode == "fast"
            and not bool(config.get("fast", {}).get("synthetic_fixture", False))
        )

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

        chunk["event_timestamp_utc"] = _to_timestamp_utc(chunk["timestamp"], timestamp_unit)
        chunk["conversion_timestamp_utc"] = _to_timestamp_utc(
            chunk["conversion_timestamp"], timestamp_unit
        )
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

        conversion_flag = _to_numeric(chunk["conversion"]).eq(1)
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
        candidates["decision_cell_id"] = make_decision_cell_id(
            candidates["campaign_id"], candidates["source_date_utc"]
        )
        candidates["arrival_anchor_cell_id"] = make_decision_cell_id(
            candidates["campaign_id"], candidates["arrival_date_utc"]
        )
        candidates["is_click"] = _to_numeric(candidates["click"]).fillna(0).eq(1)
        candidates["is_logged_attributed"] = (
            _to_numeric(candidates["attribution"]).fillna(0).eq(1)
        )
        candidate_chunks.append(
            candidates[
                [
                    "raw_row_id",
                    "user_id",
                    "conversion_id",
                    "campaign_id",
                    "event_timestamp_utc",
                    "conversion_timestamp_utc",
                    "source_date_utc",
                    "arrival_date_utc",
                    "decision_cell_id",
                    "arrival_anchor_cell_id",
                    "source_lag_days",
                    "is_click",
                    "is_logged_attributed",
                ]
            ].copy()
        )

    if observed_start is None or observed_end is None:
        raise DataContractError("No valid event timestamps were observed in the input log.")
    if not candidate_chunks:
        raise DataContractError("No valid delayed-conversion candidate rows were constructed.")
    if not impression_aggregates:
        raise DataContractError("No decision-cell impression counts were constructed.")

    candidates = pd.concat(candidate_chunks, ignore_index=True)
    impressions = pd.concat(impression_aggregates, ignore_index=True)
    impression_counts = (
        impressions.groupby(
            ["decision_cell_id", "campaign_id", "source_date_utc"],
            sort=False,
            observed=True,
        )["eligible_impression_count"]
        .sum()
        .reset_index()
    )
    impression_counts["eligible_impression_count"] = impression_counts[
        "eligible_impression_count"
    ].astype(np.int64)

    # Exact duplicate candidate rows are removed deterministically. Rows that differ
    # in click or logged-attribution status remain distinct source events.
    exact_key = [
        "user_id",
        "conversion_id",
        "campaign_id",
        "event_timestamp_utc",
        "conversion_timestamp_utc",
        "is_click",
        "is_logged_attributed",
    ]
    candidates["exact_row_signature"] = _stable_hash_strings(candidates, exact_key)
    exact_duplicate_count = int(candidates.duplicated("exact_row_signature", keep="first").sum())
    candidates = candidates.drop_duplicates("exact_row_signature", keep="first").copy()
    candidates["source_event_id"] = candidates["exact_row_signature"]
    candidates = candidates.drop(columns="exact_row_signature")

    observed_start = pd.Timestamp(observed_start).tz_convert("UTC")
    observed_end = pd.Timestamp(observed_end).tz_convert("UTC")
    candidates = candidates[
        candidates["conversion_timestamp_utc"].le(observed_end)
    ].copy()
    candidates["has_complete_lookback"] = (
        candidates["conversion_timestamp_utc"]
        - pd.to_timedelta(candidate_window_days, unit="D")
    ).ge(observed_start)

    candidates["journey_id"] = candidates["conversion_id"].astype("string")
    candidates = candidates.sort_values(
        ["journey_id", "event_timestamp_utc", "campaign_id", "source_event_id"],
        kind="stable",
    ).reset_index(drop=True)

    audit = {
        "raw_row_count": int(raw_row_count),
        "sampled_row_count": int(sampled_row_count),
        "invalid_event_timestamp_count": int(invalid_timestamp_count),
        "conversion_candidate_count_before_timing": int(
            conversion_candidate_count_before_timing
        ),
        "candidate_row_count_before_exact_deduplication": int(
            len(candidates) + exact_duplicate_count
        ),
        "exact_duplicate_candidate_count": int(exact_duplicate_count),
        "candidate_row_count_after_exact_deduplication": int(len(candidates)),
        "ambiguous_duplicate_count": 0,
        "observed_start_utc": observed_start.isoformat(),
        "observed_end_utc": observed_end.isoformat(),
    }
    return PreparedRawData(
        candidates=candidates,
        impression_counts=impression_counts,
        observed_start_utc=observed_start,
        observed_end_utc=observed_end,
        audit=audit,
        input_manifest=manifest,
    )


def write_json(payload: Any, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True, default=str)


def write_frame(
    frame: pd.DataFrame,
    path_without_suffix: str | Path,
    *,
    table_format: str,
    index: bool = False,
) -> Path:
    base = Path(path_without_suffix)
    base.parent.mkdir(parents=True, exist_ok=True)
    if table_format == "csv":
        path = base.with_suffix(".csv")
        frame.to_csv(path, index=index)
        return path
    if table_format == "parquet":
        try:
            import pyarrow  # noqa: F401
        except ImportError as exc:
            raise ConfigurationError(
                "Full mode requires pyarrow for the frozen Parquet output contract. "
                "Install requirements.txt; no CSV fallback is applied."
            ) from exc
        path = base.with_suffix(".parquet")
        frame.to_parquet(path, index=index)
        return path
    raise ConfigurationError(f"Unsupported table format: {table_format!r}")


def atomic_write_text(text: str, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, output)

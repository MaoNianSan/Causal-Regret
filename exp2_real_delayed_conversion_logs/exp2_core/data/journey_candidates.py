from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from contracts import require_columns

from .ingestion import RawScanResult


def _stable_hash_strings(frame: pd.DataFrame, columns: Iterable[str]) -> pd.Series:
    require_columns(frame.columns, columns, context="stable hash")
    hashes = pd.util.hash_pandas_object(frame[list(columns)], index=False, categorize=True)
    return hashes.map(lambda value: f"{int(value):016x}").astype("string")


def finalize_candidates(
    scan: RawScanResult,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp, pd.Timestamp, int]:
    candidates = pd.concat(scan.candidate_chunks, ignore_index=True)
    impressions = pd.concat(scan.impression_aggregates, ignore_index=True)
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
    observed_start = pd.Timestamp(scan.observed_start).tz_convert("UTC")
    observed_end = pd.Timestamp(scan.observed_end).tz_convert("UTC")
    candidates = candidates[candidates["conversion_timestamp_utc"].le(observed_end)].copy()
    candidates["has_complete_lookback"] = (
        candidates["conversion_timestamp_utc"]
        - pd.to_timedelta(scan.candidate_window_days, unit="D")
    ).ge(observed_start)
    candidates["journey_id"] = candidates["conversion_id"].astype("string")
    candidates = candidates.sort_values(
        ["journey_id", "event_timestamp_utc", "campaign_id", "source_event_id"],
        kind="stable",
    ).reset_index(drop=True)
    candidates["observed_exposure_start_utc"] = observed_start
    candidates["observed_exposure_end_utc"] = observed_end
    return candidates, impression_counts, observed_start, observed_end, exact_duplicate_count

from __future__ import annotations

from typing import Any

import pandas as pd

from .ingestion import RawScanResult


def build_raw_audit(
    scan: RawScanResult,
    candidates: pd.DataFrame,
    observed_start: pd.Timestamp,
    observed_end: pd.Timestamp,
    exact_duplicate_count: int,
) -> dict[str, Any]:
    return {
        "raw_row_count": int(scan.raw_row_count),
        "sampled_row_count": int(scan.sampled_row_count),
        "invalid_event_timestamp_count": int(scan.invalid_timestamp_count),
        "conversion_candidate_count_before_timing": int(scan.conversion_candidate_count_before_timing),
        "candidate_row_count_before_exact_deduplication": int(len(candidates) + exact_duplicate_count),
        "exact_duplicate_candidate_count": int(exact_duplicate_count),
        "candidate_row_count_after_exact_deduplication": int(len(candidates)),
        "ambiguous_duplicate_count": 0,
        "observed_start_utc": observed_start.isoformat(),
        "observed_end_utc": observed_end.isoformat(),
    }

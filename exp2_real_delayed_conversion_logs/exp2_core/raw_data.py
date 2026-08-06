from __future__ import annotations

from pathlib import Path
from typing import Any

from .data.ingestion import (
    INPUT_SCHEMA_VERSION,
    build_input_manifest,
    canonical_json_hash,
    file_sha256,
    input_manifest_identity_hash,
    load_config,
    scan_raw_log,
)
from .data.io import atomic_write_text, write_frame, write_json
from .data.journey_candidates import finalize_candidates
from .data.models import PreparedRawData
from .data.temporal_coverage import build_raw_audit
from .data.temporal_filters import make_decision_cell_id, normalize_identifier, normalize_user_identifier


def prepare_raw_log(
    input_path: str | Path,
    config: dict[str, Any],
    *,
    mode: str,
    progress: bool = True,
    apply_fast_hash_sample: bool | None = None,
) -> PreparedRawData:
    """Read the log once and construct route-independent candidates and exposure counts."""
    scan = scan_raw_log(
        input_path,
        config,
        mode=mode,
        progress=progress,
        apply_fast_hash_sample=apply_fast_hash_sample,
    )
    candidates, impression_counts, observed_start, observed_end, duplicate_count = finalize_candidates(scan)
    audit = build_raw_audit(scan, candidates, observed_start, observed_end, duplicate_count)
    return PreparedRawData(
        candidates=candidates,
        impression_counts=impression_counts,
        observed_start_utc=observed_start,
        observed_end_utc=observed_end,
        audit=audit,
        input_manifest=scan.input_manifest,
    )


__all__ = [
    "INPUT_SCHEMA_VERSION",
    "PreparedRawData",
    "atomic_write_text",
    "build_input_manifest",
    "canonical_json_hash",
    "file_sha256",
    "input_manifest_identity_hash",
    "load_config",
    "make_decision_cell_id",
    "normalize_identifier",
    "normalize_user_identifier",
    "prepare_raw_log",
    "write_frame",
    "write_json",
]

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class PreparedRawData:
    candidates: pd.DataFrame
    impression_counts: pd.DataFrame
    observed_start_utc: pd.Timestamp
    observed_end_utc: pd.Timestamp
    audit: dict[str, Any]
    input_manifest: dict[str, Any]

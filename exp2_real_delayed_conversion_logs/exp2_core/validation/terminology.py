from __future__ import annotations

from typing import Any

import pandas as pd

from contracts import DISALLOWED_RESULT_TERMS, ScientificInvariantError


def check_no_disallowed_columns(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    violations: list[str] = []
    for frame_name, frame in frames.items():
        for column in frame.columns:
            lowered = str(column).lower()
            for term in DISALLOWED_RESULT_TERMS:
                if term in lowered:
                    violations.append(f"{frame_name}.{column}")
    if violations:
        raise ScientificInvariantError(
            f"Out-of-scope result terminology found: {violations[:20]}"
        )
    return {"check": "no_out_of_scope_result_terms", "status": "PASS"}

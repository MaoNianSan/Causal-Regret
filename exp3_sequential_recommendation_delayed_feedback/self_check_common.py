"""Small shared primitives for independent Exp3 reconstruction checks."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def add_check(
    rows: list[dict[str, object]],
    check_id: str,
    passed: bool,
    detail: str,
    category: str,
) -> None:
    rows.append(
        {
            "check_id": check_id,
            "category": category,
            "status": "PASS" if passed else "FAIL",
            "detail": detail,
        }
    )


def frames_equal(left: pd.DataFrame, right: pd.DataFrame, keys: list[str]) -> bool:
    left = left.sort_values(keys).reset_index(drop=True)
    right = right.sort_values(keys).reset_index(drop=True)
    if list(left.columns) != list(right.columns) or len(left) != len(right):
        return False
    for column in left.columns:
        if left[column].dtype == object or right[column].dtype == object:
            if not left[column].astype(str).equals(right[column].astype(str)):
                return False
        elif not np.allclose(
            left[column].to_numpy(float),
            right[column].to_numpy(float),
            equal_nan=True,
        ):
            return False
    return True

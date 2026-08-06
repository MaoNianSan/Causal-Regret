from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from contracts import ConfigurationError


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

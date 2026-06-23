"""I/O utilities for CSV-first experiment outputs.

Functions:
- ensure_dir(path)
- write_rows_csv(path, rows, fieldnames=None, append=True)
- safe_float(x), safe_int(x), safe_bool(x)
- now_timestamp()
- compute_config_hash(config)

Behavior:
- Missing values written as 'NA'
- Booleans written as 0/1
- If rows is empty and file does not exist, no file is created
"""

from pathlib import Path
import csv
import hashlib
import datetime
from typing import Any, Dict, List, Optional


def ensure_dir(path: Path | str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _normalize_value(v: Any) -> Any:
    if v is None:
        return "NA"
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, float):
        # preserve precision
        return repr(v)
    return v


def write_rows_csv(
    path: Path | str,
    rows: List[Dict[str, Any]],
    fieldnames: Optional[List[str]] = None,
    append: bool = True,
) -> None:
    path = Path(path)
    if not rows:
        # do not create empty CSV without header
        return
    ensure_dir(path.parent)
    mode = "a" if append and path.exists() else "w"
    if fieldnames is None:
        # derive stable header from first row
        fieldnames = list(rows[0].keys())
    with path.open(mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if mode == "w":
            writer.writeheader()
        for r in rows:
            normalized = {k: _normalize_value(r.get(k, None)) for k in fieldnames}
            writer.writerow(normalized)


def safe_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def safe_int(x: Any) -> Optional[int]:
    try:
        return int(x)
    except Exception:
        return None


def safe_bool(x: Any) -> Optional[int]:
    if x is None:
        return None
    if isinstance(x, bool):
        return int(x)
    if str(x).lower() in {"1", "true", "t", "yes"}:
        return 1
    if str(x).lower() in {"0", "false", "f", "no"}:
        return 0
    return None


def now_timestamp() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def compute_config_hash(config: Dict[str, Any]) -> str:
    serial = repr(sorted(config.items()))
    return hashlib.sha256(serial.encode("utf-8")).hexdigest()[:10]

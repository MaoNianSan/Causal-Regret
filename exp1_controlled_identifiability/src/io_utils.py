import csv
import gzip
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

NA = "NA"


def ensure_dir(path):
    """Create a directory if it does not already exist."""
    Path(path).mkdir(parents=True, exist_ok=True)


def now_timestamp():
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def compute_config_hash(config_dict):
    """Return a stable hash for a JSON-serializable config dictionary."""
    payload = json.dumps(config_dict, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _clean_value(value):
    if value is None:
        return NA
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return NA
        return repr(float(value))
    return value


def _open_text_file(path, mode):
    path = Path(path)
    ensure_dir(path.parent)
    if str(path).endswith(".gz"):
        return gzip.open(path, mode=mode, encoding="utf-8", newline="")
    return path.open(mode, newline="", encoding="utf-8")


def write_rows_csv(path, rows, fieldnames=None, append=False):
    """Write rows to CSV with stable headers and NA missing values."""
    rows = list(rows or [])
    path = Path(path)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row.keys():
                if key not in fieldnames:
                    fieldnames.append(key)
    if not fieldnames:
        raise ValueError(f"Cannot write {path}: empty fieldnames")
    mode = "a" if append and path.exists() else "w"
    with _open_text_file(path, mode) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if mode == "w":
            writer.writeheader()
        for row in rows:
            writer.writerow({key: _clean_value(row.get(key)) for key in fieldnames})


def open_csv_writer(path, fieldnames, append=False):
    """Open a CSV writer for streaming rows, handling gzip paths."""
    path = Path(path)
    mode = "a" if append and path.exists() else "w"
    handle = _open_text_file(path, mode)
    writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
    if mode == "w":
        writer.writeheader()
    return handle, writer


def append_csv_row(writer, row, fieldnames):
    """Append one row to a CSV writer with clean values."""
    writer.writerow({key: _clean_value(row.get(key)) for key in fieldnames})


def flush_every_n_rows(file_handle, n=1000):
    """Flush the CSV file handle every n rows to keep memory use low."""
    if hasattr(file_handle, "flush"):
        file_handle.flush()


def safe_float(value):
    """Convert a CSV value to float, returning None for NA."""
    if value in (None, "", NA):
        return None
    return float(value)


def safe_int(value):
    """Convert a CSV value to int, returning None for NA."""
    if value in (None, "", NA):
        return None
    return int(float(value))


def safe_bool(value):
    """Convert a CSV value to 0/1 integer, returning None for NA."""
    if value in (None, "", NA):
        return None
    return int(bool(int(float(value))))

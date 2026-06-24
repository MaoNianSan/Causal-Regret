from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import numpy as np
import pandas as pd
import yaml

SECONDS_PER_DAY = 86400.0

# Identifiers are read as strings to avoid floating-point coercion of large
# conversion IDs.  These tokens are treated as missing after CSV round-trips.
_MISSING_IDENTIFIER_TOKENS = {"", "nan", "none", "null", "<na>", "na"}
_SENTINEL_MINUS_ONE_TOKENS = {"-1", "-1.0"}


def normalise_identifier(
    values: pd.Series,
    additional_missing_tokens: Iterable[str] | None = None,
) -> pd.Series:
    """Return a nullable string identifier with explicit missing-value handling.

    The raw Criteo log may contain numeric-looking IDs, empty values, or values
    that become ``nan`` after an intermediate CSV read.  This helper preserves
    IDs as strings and never converts missing values into the literal ID
    ``"nan"``.  Field-specific sentinels are supplied through
    ``additional_missing_tokens`` rather than being applied globally, because
    campaign identifiers have different semantics from UID/conversion IDs.
    """
    result = values.astype("string").str.strip()
    tokens = set(_MISSING_IDENTIFIER_TOKENS)
    if additional_missing_tokens:
        tokens.update(str(token).strip().casefold() for token in additional_missing_tokens)
    missing = result.isna() | result.str.casefold().isin(tokens)
    return result.mask(missing, pd.NA)


def sentinel_minus_one_mask(values: pd.Series) -> pd.Series:
    """Return a boolean mask for documented ``-1`` sentinel identifiers."""
    result = values.astype("string").str.strip().str.casefold()
    return result.isin(_SENTINEL_MINUS_ONE_TOKENS).fillna(False)


def normalise_uid_identifier(values: pd.Series) -> pd.Series:
    """Normalize a UID and treat documented ``-1`` values as missing.

    UID ``-1`` must not become a bootstrap cluster because it denotes an
    anonymous or unavailable identifier in the local input contract.
    """
    return normalise_identifier(values, _SENTINEL_MINUS_ONE_TOKENS)


def normalise_conversion_identifier(values: pd.Series) -> pd.Series:
    """Normalize a conversion ID and treat documented ``-1`` sentinels as missing."""
    return normalise_identifier(values, _SENTINEL_MINUS_ONE_TOKENS)


def identifier_mask(values: pd.Series, additional_missing_tokens: Iterable[str] | None = None) -> pd.Series:
    """Boolean validity mask corresponding to :func:`normalise_identifier`."""
    return normalise_identifier(values, additional_missing_tokens).notna()


def validate_exp2_config(cfg: Dict[str, Any]) -> None:
    """Reject stale route IDs and invalid reporting contracts before a run starts."""
    experiment_id = str(cfg.get("experiment", {}).get("experiment_id", ""))
    if experiment_id != "exp2_logged_attribution_sensitivity":
        return
    routes = cfg.get("attribution_routes", {})
    reporting = cfg.get("reporting", {})
    action = cfg.get("action", {})
    gates = cfg.get("scientific_gates", {})
    main = list(map(str, routes.get("main", [])))
    route_order = list(map(str, routes.get("route_order", [])))
    main_figure = list(map(str, reporting.get("main_figure_routes", [])))
    core = list(map(str, reporting.get("core_source_routes", [])))
    pairwise = list(map(str, reporting.get("pairwise_overlap_routes", [])))
    if str(action.get("action_unit", "")) != "campaign_source_day_cell":
        raise ValueError("Exp2 configuration requires action.action_unit=campaign_source_day_cell.")
    if "arrival_bin_anchor" not in main:
        raise ValueError("Exp2 configuration requires attribution_routes.main to contain arrival_bin_anchor.")
    stale_locations = {
        "attribution_routes.main": main,
        "attribution_routes.route_order": route_order,
        "reporting.main_figure_routes": main_figure,
        "reporting.core_source_routes": core,
        "reporting.pairwise_overlap_routes": pairwise,
    }
    stale = [name for name, values in stale_locations.items() if "arrival_time_naive" in values]
    if stale:
        raise ValueError(
            "Stale Exp2 route identifier arrival_time_naive is not supported. "
            "Use arrival_bin_anchor. Found in: " + ", ".join(stale)
        )
    if not main_figure or main_figure[0] != "arrival_bin_anchor":
        raise ValueError("reporting.main_figure_routes must start with arrival_bin_anchor.")
    if "soft_attribution_em" in main_figure:
        raise ValueError("soft_attribution_em is appendix-only and must not appear in reporting.main_figure_routes.")
    if not set(main_figure).issubset(set(main)):
        raise ValueError("reporting.main_figure_routes must be a subset of attribution_routes.main.")
    if not core or not set(core).issubset(set(main)):
        raise ValueError("reporting.core_source_routes must be a nonempty subset of attribution_routes.main.")
    if "arrival_bin_anchor" in core:
        raise ValueError("reporting.core_source_routes must exclude arrival_bin_anchor.")
    if not pairwise or not set(pairwise).issubset(set(core)):
        raise ValueError("reporting.pairwise_overlap_routes must contain only configured core source routes.")
    required_gates = {
        "min_decision_cell_ambiguity_rate",
        "min_core_pairwise_tv",
        "min_em_positive_entropy_share",
        "max_top_k_must_be_strictly_below_action_universe",
    }
    missing_gates = sorted(required_gates.difference(gates))
    if missing_gates:
        raise ValueError("Exp2 scientific_gates is missing: " + ", ".join(missing_gates))


def input_file_identity(path: str | Path, sample_bytes: int = 1_048_576) -> Dict[str, Any]:
    """Return a lightweight reproducibility identity without hashing a huge raw log in full."""
    source = Path(path).resolve()
    stat = source.stat()
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        first = handle.read(sample_bytes)
        digest.update(first)
        if stat.st_size > sample_bytes:
            handle.seek(max(stat.st_size - sample_bytes, 0))
            digest.update(handle.read(sample_bytes))
    return {
        "path": str(source),
        "size_bytes": int(stat.st_size),
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "partial_sha256": digest.hexdigest(),
        "partial_sha256_scheme": f"sha256(first_{sample_bytes}_bytes_plus_last_{sample_bytes}_bytes)",
    }

def load_config(path: str | Path = "config_exp2.yaml") -> Dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    if not isinstance(cfg, dict):
        raise ValueError(f"Configuration must be a mapping: {path}")
    cfg["_config_path"] = str(path.resolve())
    runtime = cfg.get("runtime", {}) if isinstance(cfg.get("runtime", {}), dict) else {}
    declared_root = runtime.get("project_root")
    project_root = (path.resolve().parent / declared_root).resolve() if declared_root else path.resolve().parent
    cfg["_project_root"] = str(project_root)
    cfg["_config_hash"] = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    validate_exp2_config(cfg)
    return cfg


def resolve_path(cfg: Dict[str, Any], value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path(cfg.get("_project_root", ".")) / path


def get_col(cfg: Dict[str, Any], key: str) -> str:
    return str(cfg.get("columns", {}).get(key, key))


def out_dir(cfg: Dict[str, Any], key: str) -> Path:
    return resolve_path(cfg, cfg["outputs"][key])


def ensure_output_dirs(cfg: Dict[str, Any]) -> None:
    required = ["root", "metadata", "precheck", "raw", "processed", "summaries", "tables", "figures", "checks", "legacy", "self_check"]
    for key in required:
        out_dir(cfg, key).mkdir(parents=True, exist_ok=True)
    root = out_dir(cfg, "root")
    for relative in ["figures/pdf", "figures/png", "figures/data", "figures/metadata"]:
        (root / relative).mkdir(parents=True, exist_ok=True)


def save_config_snapshot(cfg: Dict[str, Any]) -> None:
    ensure_output_dirs(cfg)
    source = Path(cfg["_config_path"])
    (out_dir(cfg, "metadata") / "config_snapshot.yaml").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def save_run_metadata(cfg: Dict[str, Any], status: str, extra: Optional[Dict[str, Any]] = None) -> None:
    ensure_output_dirs(cfg)
    payload: Dict[str, Any] = {
        "experiment_id": cfg["experiment"]["experiment_id"],
        "title": cfg["experiment"]["title"],
        "raw_data_file": cfg["data"]["raw_file"],
        "raw_input_identity": cfg.get("runtime", {}).get("input_identity"),
        "config_file": cfg["_config_path"],
        "config_hash": cfg["_config_hash"],
        "python_version": sys.version,
        "platform": platform.platform(),
        "pandas_version": pd.__version__,
        "numpy_version": np.__version__,
        "status": status,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if extra:
        payload.update(extra)
    (out_dir(cfg, "metadata") / "run_metadata.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def read_chunks(cfg: Dict[str, Any], usecols: Optional[list[str]] = None, nrows: Optional[int] = None) -> Iterable[pd.DataFrame]:
    path = resolve_path(cfg, cfg["data"]["raw_file"])
    if not path.exists():
        raise FileNotFoundError(f"Raw data file not found: {path}")
    remaining = nrows
    identifier_keys = ("uid", "campaign", "conversion_id")
    identifier_dtypes = {
        get_col(cfg, key): "string"
        for key in identifier_keys
        if get_col(cfg, key)
    }
    for chunk in pd.read_csv(
        path,
        sep=cfg["data"].get("sep", "\t"),
        usecols=usecols,
        chunksize=int(cfg["data"].get("chunk_size", 500_000)),
        low_memory=False,
        dtype=identifier_dtypes,
    ):
        if remaining is not None:
            if remaining <= 0:
                break
            chunk = chunk.iloc[:remaining].copy()
            remaining -= len(chunk)
        yield normalize_numeric_columns(chunk, cfg)
        if remaining is not None and remaining <= 0:
            break


def normalize_numeric_columns(frame: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
    numeric = ["timestamp", "conversion", "conversion_timestamp", "attribution", "click", "click_pos", "click_nb", "time_since_last_click", "cost", "cpo"]
    for key in numeric:
        column = get_col(cfg, key)
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def add_time_columns(frame: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
    ts, cts, conversion = get_col(cfg, "timestamp"), get_col(cfg, "conversion_timestamp"), get_col(cfg, "conversion")
    if ts in frame:
        frame["day_index"] = np.floor(pd.to_numeric(frame[ts], errors="coerce") / SECONDS_PER_DAY).astype("Int64")
    if all(column in frame for column in (ts, cts, conversion)):
        valid = frame[conversion].eq(1) & frame[cts].gt(frame[ts])
        frame["valid_conversion_flag"] = valid.astype(int)
        frame["delay_seconds"] = np.where(valid, frame[cts] - frame[ts], np.nan)
        frame["delay_days"] = frame["delay_seconds"] / SECONDS_PER_DAY
        frame["conversion_day_index"] = np.where(valid, np.floor(frame[cts] / SECONDS_PER_DAY), np.nan)
    return frame


def write_csv(frame: pd.DataFrame, path: str | Path, index: bool = False) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=index)


def append_csv(frame: pd.DataFrame, path: str | Path, header: bool) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, mode="a", index=False, header=header)


def ci_from_values(values: np.ndarray, level: float = 0.95) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return float("nan"), float("nan")
    alpha = 1.0 - float(level)
    return float(np.quantile(values, alpha / 2.0)), float(np.quantile(values, 1.0 - alpha / 2.0))


def make_output_manifest(cfg: Dict[str, Any]) -> None:
    root = out_dir(cfg, "root")
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        n_rows = n_columns = None
        description = ""
        if path.suffix.lower() == ".csv":
            try:
                head = pd.read_csv(path, nrows=5)
                n_columns = len(head.columns)
                with path.open("rb") as handle:
                    n_rows = max(sum(1 for _ in handle) - 1, 0)
            except Exception as exc:
                description = f"manifest read warning: {exc}"
        rows.append({
            "file_path": str(path.relative_to(Path(cfg["_project_root"]))),
            "file_type": path.suffix.lower().lstrip("."),
            "description": description,
            "created_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
            "n_rows": n_rows,
            "n_columns": n_columns,
            "required_for_paper": "",
        })
    write_csv(pd.DataFrame(rows), out_dir(cfg, "metadata") / "output_manifest.csv")

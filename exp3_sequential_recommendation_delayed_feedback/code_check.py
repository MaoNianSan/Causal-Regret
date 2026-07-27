"""Static code and naming audit for the active Exp3 implementation."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pandas as pd

from config import DEFAULT_CONFIG


def main() -> None:
    root = Path(__file__).resolve().parent
    rows: list[dict[str, object]] = []
    excluded = {"outputs", "inputs", "docs", "tests", "__pycache__"}
    for path in sorted(root.glob("*.py")):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            rows.append({"check_id": f"syntax::{path.name}", "status": "PASS", "detail": "AST parse succeeded"})
        except SyntaxError as exc:
            rows.append({"check_id": f"syntax::{path.name}", "status": "FAIL", "detail": str(exc)})
    expected_routes = ("arrival_carrier", "history_mean_control", "ridge_proxy")
    rows.append(
        {
            "check_id": "primary_route_ids",
            "status": "PASS" if DEFAULT_CONFIG.primary_route_ids == expected_routes else "FAIL",
            "detail": str(DEFAULT_CONFIG.primary_route_ids),
        }
    )
    rows.append(
        {
            "check_id": "residual_candidate_contract",
            "status": "PASS" if DEFAULT_CONFIG.include_residual_in_candidate_set is False else "FAIL",
            "detail": "Residual bucket is accounting-only",
        }
    )
    rows.append(
        {
            "check_id": "independent_hash_salts",
            "status": "PASS" if DEFAULT_CONFIG.group_hash_salt != DEFAULT_CONFIG.reference_fold_hash_salt else "FAIL",
            "detail": "Group and reference fold salts differ",
        }
    )
    report = pd.DataFrame(rows)
    status = "PASS" if (report["status"] == "PASS").all() else "FAIL"
    print(f"code_check_status={status}")
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

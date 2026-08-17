from __future__ import annotations

import json
from pathlib import Path

from exp4.configuration.run_modes import mode_settings
from exp4.configuration.schema import RESULT_SCHEMA
from exp4.validation.static_checks import run_static_checks


def test_run_modes_and_static_contract() -> None:
    root = Path(__file__).resolve().parents[2]
    assert mode_settings("fast").module_a_seed_count == 3
    assert mode_settings("middle").module_b_replications == 100
    assert mode_settings("full").bootstrap_replications == 2000
    assert not mode_settings("fast").promotion_allowed
    assert not mode_settings("middle").promotion_allowed
    checks = run_static_checks(root)
    assert checks["status"] == "PASS", json.dumps(checks, indent=2)
    assert RESULT_SCHEMA == "exp4_controlled_route_audit_v3"

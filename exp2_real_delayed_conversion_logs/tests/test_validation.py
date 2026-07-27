from __future__ import annotations

from validation import validate_frozen_configuration


def test_frozen_configuration(experiment_objects):
    checks = validate_frozen_configuration(experiment_objects["config"])
    assert checks
    assert all(check["status"] == "PASS" for check in checks)

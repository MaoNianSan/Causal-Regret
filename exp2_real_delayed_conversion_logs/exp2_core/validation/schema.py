from __future__ import annotations

from typing import Any

import numpy as np

from contracts import PRIMARY_ROUTE_ORDER, ConfigurationError


def validate_frozen_configuration(config: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    expected_primary = list(PRIMARY_ROUTE_ORDER)
    observed_primary = list(config["routes"]["primary"])
    if observed_primary != expected_primary:
        raise ConfigurationError(
            f"Primary route order changed: expected={expected_primary}, observed={observed_primary}"
        )
    checks.append({"check": "primary_route_order", "status": "PASS"})
    if bool(config["cohort"].get("modal_campaign_fallback", True)) is not False:
        raise ConfigurationError("Modal-campaign fallback must remain prohibited.")
    checks.append({"check": "modal_campaign_fallback_prohibited", "status": "PASS"})
    if str(config["input"].get("timezone", "")).upper() != "UTC":
        raise ConfigurationError("Experiment 2 timestamps must be interpreted in UTC.")
    checks.append({"check": "utc_time_standard", "status": "PASS"})
    if int(config["ranking"]["primary_top_k"]) != 10:
        raise ConfigurationError("Primary top-k is frozen at 10.")
    checks.append({"check": "primary_top_k", "status": "PASS"})
    if str(config["ranking"]["kendall_variant"]) != "tau_b":
        raise ConfigurationError("Kendall variant is frozen at tau_b.")
    checks.append({"check": "kendall_tau_b", "status": "PASS"})
    half_life = float(config["routes"]["time_decay"].get("half_life_days", 0.0))
    if not np.isclose(half_life, 1.38629436112, atol=1e-10, rtol=0.0):
        raise ConfigurationError("Time-decay half-life is frozen at 1.38629436112 days.")
    checks.append({"check": "time_decay_half_life", "status": "PASS"})
    if str(config["resampling"].get("unit")) != "uid":
        raise ConfigurationError("UID-cluster resampling is required.")
    if list(config["resampling"].get("reported_quantiles", [])) != [0.025, 0.5, 0.975]:
        raise ConfigurationError("Resampling quantiles must be q025/q500/q975.")
    if bool(config["resampling"].get("inferential_interpretation", True)):
        raise ConfigurationError("UID-resampling ranges are descriptive, not inferential.")
    checks.append({"check": "uid_resampling_contract", "status": "PASS"})
    return checks

"""Tests for the Monte Carlo precision gating rules."""

from __future__ import annotations

import pandas as pd
import pytest

from exp4.validation.precision_checks import (
    primary_contrast_contract,
    promotion_precision_checks,
    validate_monte_carlo_precision,
)


def _contrasts(
    primary_gate: str,
    run_tier_note: str = "full",
    nonprimary_gate: str = "REPORTED_NOT_GATED",
    primary_count: int = 1,
) -> pd.DataFrame:
    records = []
    for index in range(12):
        is_primary = index == 0 and primary_count >= 1
        if index == 1 and primary_count >= 2:
            is_primary = True
        gate = primary_gate if is_primary else nonprimary_gate
        records.append(
            {
                "contrast_id": f"c_{index}",
                "is_primary_contrast": is_primary,
                "monte_carlo_precision_gate": gate,
                "paired_mean_difference": -0.03,
                "paired_mcse": 0.0002,
            }
        )
    return pd.DataFrame.from_records(records)


def test_full_run_rejects_nonfull_precision_status() -> None:
    contrasts = _contrasts(primary_gate="NOT_APPLICABLE_NON_FULL")
    result = validate_monte_carlo_precision(contrasts, "full")
    assert result.status == "FAIL"
    assert result.has_nonfull_precision_status_in_full is True
    assert result.checks["no_nonfull_precision_status_in_full_run"] is False


def test_full_run_requires_all_primary_contrasts_pass() -> None:
    contrasts = _contrasts(primary_gate="STOP_AND_REVIEW")
    result = validate_monte_carlo_precision(contrasts, "full")
    assert result.status == "FAIL"
    assert result.all_primary_gates_pass is False
    passed = _contrasts(primary_gate="PASS")
    assert validate_monte_carlo_precision(passed, "full").status == "PASS"


def test_nonprimary_contrasts_use_reported_not_gated() -> None:
    contrasts = _contrasts(primary_gate="PASS")
    result = validate_monte_carlo_precision(contrasts, "full")
    assert result.checks["nonprimary_statuses_are_reported_not_gated"] is True
    assert "REPORTED_NOT_GATED" in result.nonprimary_statuses


def test_fast_middle_allow_nonfull_precision_status() -> None:
    contrasts = _contrasts(primary_gate="NOT_APPLICABLE_NON_FULL")
    assert validate_monte_carlo_precision(contrasts, "fast").status == "PASS"
    assert validate_monte_carlo_precision(contrasts, "middle").status == "PASS"
    # But a full run with the same data fails.
    assert validate_monte_carlo_precision(contrasts, "full").status == "FAIL"


def test_promotion_rejects_invalid_primary_precision() -> None:
    run_config = {"run_tier": "full"}
    bad = _contrasts(primary_gate="NOT_APPLICABLE_NON_FULL")
    checks = promotion_precision_checks(run_config, bad)
    assert checks["primary_monte_carlo_precision_pass"] is False
    assert checks["no_nonfull_precision_status_in_full_run"] is False
    good = _contrasts(primary_gate="PASS")
    checks = promotion_precision_checks(run_config, good)
    assert checks["primary_monte_carlo_precision_pass"] is True


def test_primary_contrast_contract_is_nonempty() -> None:
    ok, details = primary_contrast_contract(_contrasts(primary_gate="PASS"))
    assert ok is True
    assert "count=1" in details
    empty = _contrasts(primary_gate="PASS", primary_count=0)
    ok, _ = primary_contrast_contract(empty)
    assert ok is False
    multiple = _contrasts(primary_gate="PASS", primary_count=2)
    ok, details = primary_contrast_contract(multiple)
    assert ok is False
    assert "count=2" in details


def test_nonfull_primary_gate_not_accepted_in_full() -> None:
    contrasts = _contrasts(primary_gate="NOT_APPLICABLE_NON_FULL")
    result = validate_monte_carlo_precision(contrasts, "full")
    assert result.checks["primary_gates_all_pass"] is False
    assert result.details.startswith("run_tier=full")


def test_aggregation_sets_primary_gate_on_primary_row() -> None:
    # Regression: primary_rows.index[0] used to select the first index label
    # (row 0) instead of the actual primary contrast row. The gate must land on
    # q_0.7_to_1__sigma_0.25 and nowhere else.
    import numpy as np
    import pandas as pd

    from exp4.configuration.parameters import MODULE_A
    from exp4.reporting.aggregate_module_a import summarize_paired_contrasts

    records = []
    for seed in range(5):
        for noise in MODULE_A.proxy_noise_sds:
            for q in MODULE_A.route_label_rates:
                records.append(
                    {
                        "route_id": "proxy_label",
                        "seed": seed,
                        "attribution_proxy_noise_sd": noise,
                        "route_label_rate": q,
                        "population_action_gap_defect": 0.3 - 0.05 * q + 0.01 * noise,
                    }
                )
    seed_level = pd.DataFrame.from_records(records)
    contrasts, _ = summarize_paired_contrasts(seed_level, bootstrap_replications=50, run_tier="full")
    primary = contrasts[contrasts["is_primary_contrast"].astype(bool)]
    assert len(primary) == 1
    assert primary["contrast_id"].iloc[0] == "q_0.7_to_1__sigma_0.25"
    assert primary["monte_carlo_precision_gate"].iloc[0] == "PASS"
    nonprimary_gates = set(
        contrasts.loc[~contrasts["is_primary_contrast"].astype(bool), "monte_carlo_precision_gate"]
    )
    assert nonprimary_gates == {"REPORTED_NOT_GATED"}
    assert not contrasts["monte_carlo_precision_gate"].eq("NOT_APPLICABLE_NON_FULL").any()

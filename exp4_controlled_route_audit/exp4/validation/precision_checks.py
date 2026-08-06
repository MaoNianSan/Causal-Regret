"""Monte Carlo precision gating for paired contrasts.

Rules (post-full-fix contract):
- Primary contrasts are identified by the boolean column ``is_primary_contrast``.
- Exactly one primary contrast is expected by design (contract check).
- For a full run every primary contrast must carry a computed gate of PASS or
  STOP_AND_REVIEW; NOT_APPLICABLE_NON_FULL is forbidden in a full run.
- For fast/middle runs the primary contrast carries NOT_APPLICABLE_NON_FULL and
  is not gated.
- Non-primary contrasts always carry REPORTED_NOT_GATED: their MCSE/interval are
  reported, they never gate promotion, independent of run tier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass
class PrecisionValidation:
    run_tier: str
    primary_contrast_count: int
    primary_contrast_ids: list[str]
    primary_gates: list[str]
    passed: int
    failed: int
    all_primary_gates_pass: bool
    has_nonfull_precision_status_in_full: bool
    nonprimary_statuses: set[str]
    status: str
    details: str = ""
    checks: dict[str, bool] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "validation": "exp4_monte_carlo_precision",
            "run_tier": self.run_tier,
            "status": self.status,
            "details": self.details,
            "checks": self.checks,
            "primary_contrast_count": self.primary_contrast_count,
            "primary_contrast_ids": self.primary_contrast_ids,
            "primary_gates": self.primary_gates,
            "passed": self.passed,
            "failed": self.failed,
            "all_primary_gates_pass": self.all_primary_gates_pass,
            "has_nonfull_precision_status_in_full": self.has_nonfull_precision_status_in_full,
            "nonprimary_statuses": sorted(self.nonprimary_statuses),
        }

    def engineering_pass(self) -> bool:
        """Whether precision gates are satisfied for this run tier.

        Full runs require every primary contrast to PASS; fast/middle runs are
        explicitly not gated (NOT_APPLICABLE_NON_FULL on the primary contrast).
        """
        if self.run_tier == "full":
            return self.all_primary_gates_pass
        return bool(self.primary_gates == ["NOT_APPLICABLE_NON_FULL"])


def primary_contrast_contract(contrasts: pd.DataFrame) -> tuple[bool, str]:
    """The design contract requires exactly one primary contrast."""
    primary = contrasts[contrasts["is_primary_contrast"].astype(bool)]
    count = len(primary)
    if count == 0:
        return False, "primary_contrast_count=0"
    if count != 1:
        return False, f"primary_contrast_count={count}; design allows exactly one"
    return True, f"primary_contrast_count={count}; id={primary['contrast_id'].iloc[0]}"


def validate_monte_carlo_precision(
    contrasts: pd.DataFrame,
    run_tier: str,
) -> PrecisionValidation:
    contract_ok, contract_details = primary_contrast_contract(contrasts)
    primary = contrasts[contrasts["is_primary_contrast"].astype(bool)].copy()
    primary_ids = primary["contrast_id"].tolist() if len(primary) else []
    primary_gates = primary["monte_carlo_precision_gate"].astype(str).tolist() if len(primary) else []

    has_nonfull_in_full = (
        run_tier == "full" and any(gate == "NOT_APPLICABLE_NON_FULL" for gate in primary_gates)
    )
    all_pass = (
        contract_ok
        and bool(primary_gates)
        and all(gate == "PASS" for gate in primary_gates)
        and not has_nonfull_in_full
    )
    passed = sum(1 for gate in primary_gates if gate == "PASS")
    failed = len(primary_gates) - passed
    nonprimary_statuses = set(
        contrasts.loc[~contrasts["is_primary_contrast"].astype(bool), "monte_carlo_precision_gate"]
        .astype(str)
    )
    checks = {
        "primary_contrast_contract_valid": contract_ok,
        "primary_gates_all_pass": all_pass,
        "no_nonfull_precision_status_in_full_run": not has_nonfull_in_full,
        "nonprimary_statuses_are_reported_not_gated": nonprimary_statuses <= {"REPORTED_NOT_GATED"},
    }
    if run_tier == "full":
        status = "PASS" if all_pass else "FAIL"
    else:
        # Fast/Middle are allowed to carry NOT_APPLICABLE_NON_FULL on the
        # primary contrast; the scientific check reports run_tier explicitly.
        nonfull_ok = contract_ok and bool(primary_gates) and not has_nonfull_in_full
        status = "PASS" if nonfull_ok else "FAIL"
    details = (
        f"run_tier={run_tier}; primary_contrasts={len(primary_ids)}; "
        f"passed={passed}; failed={failed}; ids={primary_ids}; gates={primary_gates}"
    )
    return PrecisionValidation(
        run_tier=run_tier,
        primary_contrast_count=len(primary_ids),
        primary_contrast_ids=primary_ids,
        primary_gates=primary_gates,
        passed=passed,
        failed=failed,
        all_primary_gates_pass=all_pass,
        has_nonfull_precision_status_in_full=has_nonfull_in_full,
        nonprimary_statuses=nonprimary_statuses,
        status=status,
        details=details,
        checks=checks,
    )


def promotion_precision_checks(
    run_config: dict[str, object],
    contrasts: pd.DataFrame,
) -> dict[str, bool]:
    """Promotion-level precision gates.

    Promotion must not rely only on the scientific MONTE_CARLO_PRECISION row;
    it re-derives the gates from the contrasts table and the run tier.
    """
    run_tier = str(run_config["run_tier"])
    contract_ok, _ = primary_contrast_contract(contrasts)
    primary = contrasts[contrasts["is_primary_contrast"].astype(bool)]
    primary_gates = primary["monte_carlo_precision_gate"].astype(str).tolist()
    has_nonfull_in_full = (
        run_tier == "full" and any(gate == "NOT_APPLICABLE_NON_FULL" for gate in primary_gates)
    )
    return {
        "primary_contrast_contract_valid": contract_ok,
        "primary_monte_carlo_precision_pass": (
            run_tier == "full"
            and contract_ok
            and bool(primary_gates)
            and all(gate == "PASS" for gate in primary_gates)
            and not has_nonfull_in_full
        ),
        "no_nonfull_precision_status_in_full_run": not has_nonfull_in_full,
    }


def write_precision_checks(run_dir: Path, result: PrecisionValidation) -> None:
    from exp4.outputs.writers import write_json

    write_json(result.as_dict(), run_dir / "checks" / "exp4_precision_checks.json")

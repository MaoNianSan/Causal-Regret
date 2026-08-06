from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from contracts import ConfigurationError

from .artifacts import validate_resampling_artifacts
from .schema import validate_frozen_configuration
from .scientific import validate_primary_science
from .terminology import check_no_disallowed_columns
from ..cohort_stages import validate_cohort_flow_reconciliation


@dataclass(frozen=True)
class ValidationResult:
    engineering_status: str
    scientific_status: str
    paper_promotion_status: str
    checks: list[dict[str, Any]]

    @property
    def passed(self) -> bool:
        return self.engineering_status == "PASS" and self.scientific_status == "PASS"


def validate_run(
    config: dict[str, Any],
    *,
    journey_manifest: pd.DataFrame,
    decision_cells: pd.DataFrame,
    assignments: pd.DataFrame,
    route_allocations: pd.DataFrame,
    arrival_displacement: pd.DataFrame,
    source_route_pairwise: pd.DataFrame,
    bootstrap_draws: pd.DataFrame,
    mode: str,
    expected_bootstrap_repetitions: int | None = None,
    bootstrap_audit: dict[str, Any] | None = None,
    development_override: bool = False,
    cohort_flow: pd.DataFrame | None = None,
) -> ValidationResult:
    checks = validate_frozen_configuration(config)
    checks.extend(
        validate_primary_science(
            config,
            journey_manifest=journey_manifest,
            decision_cells=decision_cells,
            assignments=assignments,
            route_allocations=route_allocations,
            arrival_displacement=arrival_displacement,
            source_route_pairwise=source_route_pairwise,
        )
    )
    if cohort_flow is not None:
        checks.append(
            validate_cohort_flow_reconciliation(journey_manifest, cohort_flow)
        )
    checks.append(
        check_no_disallowed_columns(
            {
                "journey_manifest": journey_manifest,
                "route_allocations": route_allocations,
                "arrival_displacement": arrival_displacement,
                "source_route_pairwise": source_route_pairwise,
            }
        )
    )
    checks.extend(
        validate_resampling_artifacts(
            config,
            arrival_displacement=arrival_displacement,
            source_route_pairwise=source_route_pairwise,
            bootstrap_draws=bootstrap_draws,
            mode=mode,
            expected_bootstrap_repetitions=expected_bootstrap_repetitions,
            bootstrap_audit=bootstrap_audit,
        )
    )
    if bool(config["runtime"].get("paper_result", False)):
        raise ConfigurationError("Runtime configuration cannot directly set paper_result=true.")
    checks.append({"check": "explicit_paper_promotion_only", "status": "PASS"})
    if mode == "fast":
        promotion_status = "INELIGIBLE_FAST"
    elif development_override:
        promotion_status = "BLOCKED_DEVELOPMENT_OVERRIDE"
    else:
        promotion_status = "PENDING_INDEPENDENT_PROMOTION"
    return ValidationResult(
        engineering_status="PASS",
        scientific_status="PASS",
        paper_promotion_status=promotion_status,
        checks=checks,
    )


__all__ = ["ValidationResult", "validate_frozen_configuration", "validate_run"]

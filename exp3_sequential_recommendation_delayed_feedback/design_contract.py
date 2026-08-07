"""Canonical scientific names and metadata for Experiment 3."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

import pandas as pd

from utilities import save_frame


EXPERIMENT_TITLE = "Experiment 3: Logged-Supported Ranking Recovery"
EVIDENCE_CHAIN = (
    "score recovery",
    "held-out reference-pair gap recovery",
    "logged-supported ranking recovery",
)
SUPPORT_SCOPE = "common_logged_supported_action_cells"
EVALUATION_ARRAY_SCHEMA_VERSION = "exp3_evaluation_arrays_v2"


@dataclass(frozen=True)
class MetricSpec:
    metric_id: str
    display_name: str
    estimand_level: str
    definition: str
    aggregation_unit: str
    direction: str
    primary_or_secondary: str
    support_scope: str = SUPPORT_SCOPE
    causal_interpretation: bool = False
    uncertainty_role: str = "full_sample_primary_resampling_sensitivity"
    deprecated_aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class RouteSpec:
    route_id: str
    route_display_name: str
    route_role: str
    uses_predecision_available_information: bool
    deployment_value_estimated: bool = False
    uses_future_outcome: bool = False
    uses_source_identity: bool = False


ROUTE_SPECS = {
    spec.route_id: spec
    for spec in (
        RouteSpec(
            "arrival_carrier",
            "Arrival carrier\u2014misbinding control",
            "deliberate_source_misbinding_control",
            True,
        ),
        RouteSpec(
            "history_mean_control",
            "Historical mean",
            "simple_history_control",
            True,
        ),
        RouteSpec(
            "ridge_proxy",
            "Ridge proxy",
            "history_fitted_proxy_route",
            True,
        ),
    )
}


METRIC_SPECS = (
    MetricSpec(
        "pooled_supported_cell_spearman",
        "Pooled supported-cell Spearman",
        "score",
        "Spearman correlation across common-supported action cells.",
        "supported_action_cell",
        "higher_is_better",
        "primary",
        deprecated_aliases=("score_spearman_correlation",),
    ),
    MetricSpec(
        "pooled_supported_cell_mae",
        "Pooled supported-cell MAE",
        "score",
        "Macro mean absolute error across common-supported action cells.",
        "supported_action_cell",
        "lower_is_better",
        "primary",
        deprecated_aliases=("score_calibration_mae",),
    ),
    MetricSpec(
        "exposure_weighted_supported_cell_mae",
        "Exposure-weighted supported-cell MAE",
        "score",
        "Absolute score error weighted by supported-cell exposure count.",
        "supported_action_cell",
        "lower_is_better",
        "secondary",
    ),
    MetricSpec(
        "within_audit_unit_centered_spearman",
        "Within-audit-unit centered Spearman",
        "score",
        "Spearman correlation after centering scores and targets within audit unit.",
        "supported_action_cell",
        "higher_is_better",
        "secondary",
    ),
    MetricSpec(
        "calibration_intercept",
        "Calibration intercept",
        "score",
        "Intercept from observed target regressed on route score.",
        "supported_action_cell",
        "closer_to_zero_is_better",
        "secondary",
    ),
    MetricSpec(
        "calibration_slope",
        "Calibration slope",
        "score",
        "Slope from observed target regressed on route score.",
        "supported_action_cell",
        "closer_to_one_is_better",
        "secondary",
    ),
    MetricSpec(
        "maximum_heldout_reference_pair_gap_error",
        "Maximum held-out reference-pair gap error",
        "gap",
        "Audit-unit maximum absolute error between selection-fold route gaps and held-out target gaps.",
        "audit_unit",
        "lower_is_better",
        "primary",
        deprecated_aliases=("heldout_gap_defect",),
    ),
    MetricSpec(
        "mean_absolute_reference_pair_gap_error",
        "Mean absolute reference-pair gap error",
        "gap",
        "Mean absolute error over held-out reference pairs.",
        "audit_unit",
        "lower_is_better",
        "secondary",
    ),
    MetricSpec(
        "p90_absolute_reference_pair_gap_error",
        "P90 absolute reference-pair gap error",
        "gap",
        "Ninetieth percentile absolute error over held-out reference pairs.",
        "audit_unit",
        "lower_is_better",
        "secondary",
    ),
    MetricSpec(
        "heldout_reference_pair_sign_agreement",
        "Held-out reference-pair sign agreement",
        "gap",
        "Sign agreement for non-near-tie held-out reference pairs.",
        "audit_unit",
        "higher_is_better",
        "primary",
        deprecated_aliases=("gap_sign_agreement",),
    ),
    MetricSpec(
        "valid_reference_pair_count",
        "Valid reference-pair count",
        "gap",
        "Count of supported non-reference pairs entering gap evaluation.",
        "reference_pair",
        "descriptive",
        "secondary",
        deprecated_aliases=("valid_gap_pair_count",),
    ),
    MetricSpec(
        "near_tie_pair_count",
        "Near-tie pair count",
        "gap",
        "Count of held-out reference pairs below the history-frozen near-tie threshold.",
        "reference_pair",
        "descriptive",
        "secondary",
    ),
    MetricSpec(
        "near_tie_pair_share",
        "Near-tie pair share",
        "gap",
        "Near-tie count divided by valid reference-pair count.",
        "reference_pair",
        "descriptive",
        "secondary",
    ),
    MetricSpec(
        "reference_pair_coverage",
        "Reference-pair coverage",
        "support",
        "Available reference-versus-supported-alternative pairs divided by the frozen candidate reference-pair count.",
        "audit_unit",
        "descriptive",
        "secondary",
        deprecated_aliases=("pair_coverage",),
    ),
    MetricSpec(
        "signed_cross_fitted_reference_minus_route_value_difference",
        "Signed cross-fitted reference-minus-route value difference",
        "ranking",
        "Opposite-fold target mean of the fold reference minus the route-selected action.",
        "audit_unit",
        "lower_is_better",
        "secondary",
        deprecated_aliases=("cross_fitted_ranking_shortfall",),
    ),
    MetricSpec(
        "top_action_agreement_with_fold_reference",
        "Top-action agreement with fold-selected reference",
        "ranking",
        "Agreement between route and reference actions selected in the same selection fold.",
        "audit_unit",
        "higher_is_better",
        "primary",
        deprecated_aliases=("top_action_match_rate",),
    ),
    MetricSpec(
        "ridge_over_historical_paired_value_gain",
        "Ridge-over-Historical paired value gain",
        "ranking",
        "Historical reference-minus-route difference minus the Ridge difference.",
        "audit_unit",
        "higher_is_better",
        "primary",
    ),
)

METRIC_BY_ID = {spec.metric_id: spec for spec in METRIC_SPECS}
DEPRECATED_ALIASES = {
    alias: spec.metric_id for spec in METRIC_SPECS for alias in spec.deprecated_aliases
}


def route_metadata(route_id: str) -> dict[str, object]:
    if route_id not in ROUTE_SPECS:
        raise KeyError(f"Unknown Exp3 route: {route_id}")
    return asdict(ROUTE_SPECS[route_id])


def metric_registry_frame() -> pd.DataFrame:
    rows = []
    for spec in METRIC_SPECS:
        row = asdict(spec)
        row["deprecated_aliases"] = ";".join(spec.deprecated_aliases)
        row["deprecated"] = False
        rows.append(row)
        for alias in spec.deprecated_aliases:
            alias_row = row.copy()
            alias_row.update(
                {
                    "metric_id": alias,
                    "display_name": f"Deprecated alias for {spec.metric_id}",
                    "deprecated_aliases": "",
                    "deprecated": True,
                    "canonical_metric_id": spec.metric_id,
                }
            )
            rows.append(alias_row)
    frame = pd.DataFrame(rows)
    if "canonical_metric_id" not in frame:
        frame["canonical_metric_id"] = frame["metric_id"]
    else:
        frame["canonical_metric_id"] = frame["canonical_metric_id"].fillna(frame["metric_id"])
    return frame


def design_contract_hash() -> str:
    payload = {
        "experiment_title": EXPERIMENT_TITLE,
        "evidence_chain": EVIDENCE_CHAIN,
        "routes": [asdict(ROUTE_SPECS[key]) for key in sorted(ROUTE_SPECS)],
        "metrics": [asdict(spec) for spec in METRIC_SPECS],
        "evaluation_array_schema_version": EVALUATION_ARRAY_SCHEMA_VERSION,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_metric_registry(output_dir: Path) -> Path:
    return save_frame(metric_registry_frame(), output_dir / "tables" / "exp3_metric_registry.csv")

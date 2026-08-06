"""Deprecated compatibility exports for v2 module aggregators."""

from exp4.reporting.aggregate_module_a import (
    summarize_paired_contrasts,
    summarize_population,
)
from exp4.reporting.aggregate_module_b import (
    aggregate_audit_performance,
    aggregate_selection_diagnostics,
    aggregate_weight_diagnostics,
)
from exp4.reporting.aggregate_module_c import (
    aggregate_control_summary,
    aggregate_correspondence_checks,
    aggregate_parameter_recovery,
)

__all__ = [name for name in globals() if name.startswith(("aggregate_", "summarize_"))]

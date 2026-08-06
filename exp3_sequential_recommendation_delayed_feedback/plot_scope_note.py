"""Dynamic support-scope disclosure for the Exp3 main figure."""
from __future__ import annotations

import pandas as pd

from plot_contract import evaluation_exposure_scope


def build_scope_note(support: pd.Series, action_coverage: pd.DataFrame) -> str:
    top_k, exposure_mass = evaluation_exposure_scope(action_coverage, "active_run")
    return (
        f"Top-{top_k} actions cover {exposure_mass:.1%} of evaluation exposures. "
        f"Common-supported action coverage {float(support.action_coverage):.1%}; "
        f"reference-pair coverage {float(support.reference_pair_coverage):.1%}; "
        f"audit-unit coverage {float(support.audit_unit_coverage):.1%}; "
        f"mean supported actions {float(support.supported_action_count_mean):.2f}."
    )

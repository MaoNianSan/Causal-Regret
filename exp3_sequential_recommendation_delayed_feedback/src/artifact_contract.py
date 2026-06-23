"""Named artifacts required by the Exp3 output contract."""
from __future__ import annotations

ARTIFACTS = {
    "run_manifest": "metadata/run_manifest.json",
    "input_data_manifest": "metadata/input_data_manifest.csv",
    "artifact_manifest": "metadata/artifacts_manifest.csv",
    "sequential_raw": "raw/sequential_decision_raw.csv",
    "bootstrap_summary": "summaries/user_bootstrap_metric_summary.csv",
    "proxy_calibration": "summaries/proxy_calibration_summary.csv",
    "main_figure_pdf": "figures/pdf/fig_exp3_long_term_recoverability.pdf",
    "main_figure_png": "figures/png/fig_exp3_long_term_recoverability.png",
    "main_figure_data": "figures/data/fig_exp3_long_term_recoverability_data.csv",
    "main_figure_metadata": "figures/metadata/fig_exp3_long_term_recoverability_metadata.json",
    "proxy_quality_table": "tables/tbl_app_exp3_proxy_score_quality.csv",
    "completion_report": "reports/experiment_refactor_completion_report.md",
}

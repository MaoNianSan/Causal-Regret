# Exp2 Output Contract

Exp2 evaluates observational logged credit-allocation and source-time decision-cell ranking sensitivity.
It does not estimate causal regret, online policy value, ROI, or a deployable policy comparison.

Formal figure bundles:

```text
outputs/<mode>/figures/pdf/<figure_id>.pdf
outputs/<mode>/figures/png/<figure_id>.png
outputs/<mode>/figures/data/<figure_id>_data.csv
outputs/<mode>/figures/metadata/<figure_id>_metadata.json
```

Formal figures:

- `fig_exp2_attribution_sensitivity`
- `fig_app_exp2_source_route_pairwise_overlap`

Table-only appendix diagnostics:

- `tbl_app_exp2_source_linked_audit`
- `tbl_app_exp2_top_k_sensitivity`
- `tbl_app_exp2_candidate_window_sensitivity`
- `tbl_app_exp2_em_assignment_diagnostic`

Each table-only diagnostic emits:

```text
outputs/<mode>/tables/<table_id>.csv
outputs/<mode>/tables/<table_id>.md
outputs/<mode>/tables/<table_id>.tex
```

Main figure metadata must include `metric_id`, `metric_formula_id`, `uncertainty_unit=uid`, `ci_level=0.95`, `n_bootstrap`, `input_data_status`, `paper_result`, `figure_status`, and `estimand_boundary`.

The required estimand boundary is:

```text
observational logged credit-allocation and decision-cell-ranking sensitivity; not policy value, causal effect, ROI, or online deployment evaluation
```

For this repair, figure metadata uses the explicit source-time wording:

```text
observational logged credit-allocation and source-time decision-cell ranking sensitivity; not policy value, causal effect, ROI, or deployment evaluation
```

## Clean-run and identifier safeguards

`figure_table_repair_regression.json` records `not_applicable_clean_run=true` when no explicit display-only before snapshot is supplied. In that state the clean-run semantic check passes; strict before/after SHA256 equality is enforced only for an explicit replot audit.

`exp2_conversion_uid_integrity_summary.csv` includes `candidate_rows_uid_sentinel_minus_one` and `conversion_ids_uid_sentinel_minus_one`. UID sentinels `-1` and `-1.0` are invalid bootstrap identifiers and are excluded before assignment and statistics.

Run metadata and runner status include raw-input identity fields: file path, size, modification time, and a partial SHA256 over the first and last 1 MiB.

## Candidate-window diagnostic runtime contract

Candidate-window sensitivity is an appendix-only common-cohort point-estimate diagnostic. It does not run a separate nested UID bootstrap for every window. The main route-sensitivity summary remains the sole inferential Exp2 object and reports the configured UID-bootstrap confidence intervals. Candidate-window outputs record `window_bootstrap_replicates=0` and `window_uncertainty_status=not_computed_point_estimate_common_cohort_diagnostic`.

## Self-check behavior

Self-check is non-destructive: it writes pass/fail reports but never rewrites figure metadata or figure-data status. A failed full audit prevents `finalize_exp2.py` from promoting `paper_result=true`; a transient audit failure therefore cannot corrupt an otherwise traceable figure bundle.

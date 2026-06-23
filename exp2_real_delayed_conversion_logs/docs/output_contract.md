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

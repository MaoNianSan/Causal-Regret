# Exp2 output manifest

## Formal main output

- `fig_exp2_attribution_sensitivity`
  - panel A: eligible source-to-conversion delay composition;
  - panel B: `credit_allocation_tv_distance_vs_arrival_anchor` versus `top_k_decision_cell_overlap_vs_arrival_anchor`.

## Appendix figure

- `fig_app_exp2_source_route_pairwise_overlap`
  - pairwise source-route TV distance and top-10 decision-cell overlap heatmaps.

## Appendix tables

- `tbl_app_exp2_dataset_summary`
- `tbl_app_exp2_candidate_set_summary`
- `tbl_app_exp2_attribution_routes`
- `tbl_app_exp2_source_linked_audit`
- `tbl_app_exp2_top_k_sensitivity`
- `tbl_app_exp2_candidate_window_sensitivity`
- `tbl_app_exp2_em_assignment_diagnostic`
- `tbl_app_exp2_cost_adjusted_credit_score`

## Required bundle contract

Every figure has:

```text
outputs/<mode>/figures/pdf/<figure_id>.pdf
outputs/<mode>/figures/png/<figure_id>.png
outputs/<mode>/figures/data/<figure_id>_data.csv
outputs/<mode>/figures/metadata/<figure_id>_metadata.json
```

Fast figures always have `paper_result=false`. Full figures become paper results only after `finalize_exp2.py` succeeds.

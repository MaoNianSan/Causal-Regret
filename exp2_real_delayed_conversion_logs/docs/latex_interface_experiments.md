# Exp2 LaTeX Interface

Exp2 evaluates observational logged credit-allocation and source-time decision-cell ranking sensitivity.
It does not estimate causal regret, online policy value, ROI, or a deployable policy comparison.

## Main Text

- `fig_exp2_attribution_sensitivity`

Panel A is delay composition in the eligible decision-cell cohort. Panel B maps credit-allocation TV distance from the arrival-bin anchor against top-10 source-time decision-cell overlap with that anchor.

## Appendix

- `fig_app_exp2_source_route_pairwise_overlap`
- `tbl_app_exp2_source_linked_audit`
- `tbl_app_exp2_top_k_sensitivity`
- `tbl_app_exp2_candidate_window_sensitivity`
- `tbl_app_exp2_em_assignment_diagnostic`

Do not cite source-linked audit, top-k sensitivity, candidate-window sensitivity, or EM assignment diagnostics as formal appendix figures. They are table-only diagnostics.

The arrival-bin anchor is a constructed logged diagnostic allocation, not an observed policy action or policy value estimator.

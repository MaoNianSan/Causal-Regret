# LaTeX interface for Exp3

Only full outputs with `paper_result=true` may be cited. Fast outputs are never paper results.

```latex
\includegraphics{outputs/full/figures/pdf/fig_exp3_long_term_recoverability.pdf}
\includegraphics{outputs/full/figures/pdf/fig_app_exp3_horizon_eligibility.pdf}
```

## Figure Caption Fact Sheet

- Main figure Panel A: held-out calibration; deciles; vertical bars are 95% user-bootstrap CIs.
- Main figure Panel B: 6h ranking regret; lower is better; `Reference` is offline; dashed carrier line is the carrier baseline.
- ST ridge versus History mean paired regret reduction: 0.0043, 95% CI [-0.0050, 0.0147].
- Horizon appendix: the primary 6h horizon was pre-specified; the figure reports eligibility loss due to right censoring, not engagement saturation.

## Table Input Paths

- `outputs/full/tables/tbl_app_exp3_proxy_static_control.csv`
- `outputs/full/tables/tbl_app_exp3_source_label_sensitivity.csv`
- `outputs/full/summaries/paired_effect_vs_history_mean_static.csv`
- `outputs/full/summaries/oracle_action_dynamics_summary.csv`
- `outputs/full/summaries/proxy_score_quality.csv`

## Reference Role

`source_aware_reference` is an offline reference, not a deployable method.

## Prohibited Wording

- significant outperformance over the history-only baseline
- 10% labels are sufficient
- label coverage monotonically improves recoverability
- causal regret, OPE, online policy improvement, or platform utility evaluation

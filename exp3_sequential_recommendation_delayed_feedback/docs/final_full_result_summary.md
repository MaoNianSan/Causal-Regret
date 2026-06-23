# Final full result summary

- Experiment: `exp3_long_term_recoverability`
- Primary target and horizon: `long_value_log`, `6h`
- Input status: `real_kuairand_1k`
- Run mode / paper result: `full` / `True`
- Full sample counts: `6129856` main source events, `1000` users, `1000` bootstraps, `30` label-mask trajectories
- Main figure/table ids: `fig_exp3_long_term_recoverability`, `fig_app_exp3_horizon_eligibility`, `tbl_app_exp3_proxy_static_control`, `tbl_app_exp3_source_label_sensitivity`

## Score Quality

```text
               method_id  held_out_proxy_score_target_spearman  proxy_calibration_error  top_10_overlap_with_source_aware_reference  ranking_regret_per_time_bin             fit_split   evaluation_split               target_context                      main_feature_information primary_horizon
  short_term_ridge_proxy                              0.842651                 0.020267                                    0.873589                     0.024836 history_standard_only main_standard_only same_split_standard_log_only completed_history_plus_earlier_main_bins_only              6h
history_ewma_ridge_proxy                              0.844729                 0.049571                                    0.873589                     0.024836 history_standard_only main_standard_only same_split_standard_log_only completed_history_plus_earlier_main_bins_only              6h
```

## ST Ridge Versus History Mean

- `ST ridge` ranking regret: 0.0248 [0.0085, 0.0874]
- `History mean` ranking regret: 0.0291 [0.0116, 0.0944]
- Paired regret reduction: 0.0043 [-0.0050, 0.0147]
- Interpretation: the paired interval spans zero, so the incremental decision-level gain beyond `history_mean_static` is not separately established.

## Caveats

- Partial label sensitivity uses high absolute labelled-outcome counts, e.g. q=.10 has `594595` expected labels; it is not evidence of monotonic recoverability or label sufficiency.
- Oracle action stability: `18` decision bins, `2` unique oracle top actions, switch rate 0.2353, largest top-action share 0.5000.

## Permissible Claims

- The history-fitted short-term ridge proxy achieved strong held-out alignment with the constructed 6h target.
- Its ranking-regret point estimate was lower than `history_mean_static`, but the paired 95% CI spanned zero.
- Stable action-category structure limits power to separate dynamic proxy value from history-level action differences.

## Prohibited Claims

- Do not claim significant outperformance over the history-only baseline.
- Do not claim 10% labels are sufficient or that label coverage monotonically improves recoverability.
- Do not describe Exp3 as online policy improvement, OPE, causal regret, or platform utility evaluation.

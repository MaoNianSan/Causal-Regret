# EXP1 output contract

The package is intentionally distributed without `outputs/fast` or
`outputs/full`. Create output only by running the documented entry points.

## Required summary fields

`outputs/<mode>/summaries/seed_summary.csv` includes:

- design keys: `seed`, `delay_setting`, `regime`, `method`;
- contextual estimand: `context_observed_by_all`, `regret_comparator`, `final_Rc`;
- delay audit: `mean_delay`, `trace_observed_mean_delay`, `delay_path_id`,
  `policy_dependent_delay`;
- feedback fairness: `n_observed_arrivals`, `effective_feedback_units`;
- source-binding diagnostics: `ranking_reversal_rate`,
  `source_state_mismatch_mean`, `source_context_mismatch_mean`;
- posterior attribution diagnostics: `soft_attribution_true_mass`,
  `soft_attribution_top1_accuracy`, `assignment_entropy`,
  `n_soft_assignment_events`;
- proxy and EM audits: `proxy_state_error_mean`, `em_delay_likelihood`,
  `labelled_feature_alignment_max`.

## Manifest contracts

`metadata/run_manifest.json` declares:

- the shared-path and finite-horizon calibration contract;
- action-dependent stress-test isolation;
- the Gaussian observable-state-integrated EM contract;
- proxy source-time feature consistency.

## Required figures

The self-check requires the data, PNG, PDF, and metadata bundle for:

1. `fig_exp1_validity_boundary`;
2. `fig_exp1_same_mean_delay`;
3. `fig_exp1_attribution_diagnostics`;
4. `fig_exp1_proxy_quality`.

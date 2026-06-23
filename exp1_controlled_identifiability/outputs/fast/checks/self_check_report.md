# EXP1 self-check

- [FAILED] backend completed: failed
- [PASSED] contextual estimand declared: all learners observe X_t; comparator is the conditional-risk argmin_a E[loss(a,S_t)|X_t]
- [PASSED] primary shared-path contract declared: pre-generated shared state/context/delay paths; matched by realised uncensored finite-horizon mean delay
- [PASSED] structural EM contract declared: default EM integrates P(D=d|observable source feature) under the Gaussian AR(1) state posterior by binned Gauss-Hermite quadrature; stationary geometric EM is an explicit ablation
- [PASSED] proxy feature-consistency contract declared: proxy action selection, labelled source updates, and unlabelled candidate updates all use the saved source-time Kalman proxy feature
- [PASSED] no output marked as paper result: paper_result=False
- [PASSED] seed summary schema: missing=[]
- [FAILED] expected run count: expected=792; observed=204
- [PASSED] unique design keys: duplicates=0
- [PASSED] all learners receive context: context_observed_by_all
- [PASSED] regret comparator is context-information oracle: ['context_information_oracle']
- [PASSED] causal regret finite: final_Rc
- [FAILED] seed summary readable: OverflowError('cannot convert float infinity to integer')
- [FAILED] design manifest expected count: expected=792; observed=204
- [PASSED] design manifest contains no failed row: {'completed': 204}
- [FAILED] registered diagnostic figure bundles exist: figures/data/fig_exp1_same_mean_delay_data.csv; figures/png/fig_exp1_same_mean_delay.png; figures/pdf/fig_exp1_same_mean_delay.pdf; figures/metadata/fig_exp1_same_mean_delay_metadata.json; figures/data/fig_exp1_attribution_diagnostics_data.csv; figures/png/fig_exp1_attribution_diagnostics.png; figures/pdf/fig_exp1_attribution_diagnostics.pdf; figures/metadata/fig_exp1_attribution_diagnostics_metadata.json; figures/data/fig_exp1_proxy_quality_data.csv; figures/png/fig_exp1_proxy_quality.png; figures/pdf/fig_exp1_proxy_quality.pdf; figures/metadata/fig_exp1_proxy_quality_metadata.json

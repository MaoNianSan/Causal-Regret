# Literature alignment and claim boundary

## What this experiment is

Exp3 uses KuaiRand standard-feed logs to assess whether restricted information
interfaces preserve the ranking of a **constructed six-hour future-engagement
target** on observed support. It is not a native delayed-feedback benchmark, an
off-policy estimator, or an online policy experiment.

KuaiRand includes randomly exposed videos as a separate intervention regime.
The primary Exp3 protocol does not mix that stream into only main-period target
construction, because there is no matched historical random stream used for
proxy fitting. The target is thus defined consistently from standard-feed logs
in both history and held-out main periods.

## Methodological implications

1. **Short-term signals are proxies, not matured targets.** Delayed-feedback
   work can exploit post-click signals to improve timeliness, but their
   information content and temporal mismatch must remain explicit.
2. **Logged target prediction is not policy evaluation.** A policy-value or
   online causal claim needs an identified estimand, logging-policy conditions,
   and an appropriate estimator. This diagnostic introduces none.
3. **Support restriction is evaluative.** Candidate categories are restricted to
   cells with adequate observed target support; this is not a deployable
   candidate-generation model.
4. **Partial source labels form a sensitivity regime.** Source update on a
   labelled event and carrier update otherwise is a mixed rule. No monotonicity
   theorem is asserted for the finite-sample q sweep.
5. **Chronological proxy scoring is required.** A main-period proxy may use
   completed history and earlier main bins, but cannot use a full-main-period
   statistic as an imputation or global fallback.
6. **Intervals are conditional diagnostics.** User-cluster resampling reflects
   user composition conditional on the observed calendar window, fitted proxy,
   support mask, and finite label-mask bank; it is not a full retraining or OPE
   interval.

## References for manuscript bibliography

- Gao, C., et al. (2022). *KuaiRand: An Unbiased Sequential Recommendation
  Dataset with Randomly Exposed Videos*. CIKM 2022.
- Yang, J.-Q., and Zhan, D.-C. (2022). *Generalized Delayed Feedback Model with
  Post-Click Information in Recommender Systems*. NeurIPS 2022.
- Narita, Y., Yasui, S., and Yata, K. (2021). *Debiased Off-Policy Evaluation
  for Recommendation Systems*. RecSys 2021.

Reconcile the exact citation keys with the paper's existing `.bib` file before
manuscript insertion.

# Exp4 v2 Manuscript Mapping

| Paper location | Code function or module | Output field | Figure/table | Interpretation | Claim boundary |
|---|---|---|---|---|---|
| Definition 4.3 | `exp4.metrics.action_gaps.compute_action_gap_defect` | `round_max_gap_defect`, `population_action_gap_defect` | Figure 6(a) | Mean per-round maximum action-gap defect | Not learner regret or a validity probability |
| Section 5.2 raw defect | `exp4.calibration.evaluation.evaluate_cross_fitted_calibration` | `raw_defect` | Main calibration table | Observed discrepancy in labelled audit units | Conditional on controlled full-pair evidence |
| Section 5.2 calibrated defect | same | `oof_calibrated_defect` | Main calibration table | Held-out discrepancy after pair-specific affine calibration | Does not form a coherent loss map or policy |
| Section 5.2 recoverability | same | `recoverability` | Main calibration table | Relative discrepancy reduction in the specified affine family | Not route validity or identification probability |
| Section 5.3 `n_lab` | `exp4.modules.module_b.run_module_b` | `labelled_sample_size` | Figure 6(d), appendix support table | Included audit units | Not pair coverage in ordinary logs |
| Section 5.3 `n_eff` | `exp4.audit.support.compute_effective_sample_size` | `effective_sample_size` | Figure 6(d), appendix support table | Weight-adjusted effective support | Known simulated inclusion probabilities only |
| Section 6.5 Module A | `exp4.modules.module_a.run_module_a_seed` | Module A seed and population summaries | Figure 6(a) | Controlled route-alignment boundary | `q=1` is a simulator invariant, not observational evidence |
| Section 6.5 Module B | `exp4.modules.module_b.run_module_b` | audit performance, weight, selection summaries | Figure 6(b-d) | Finite/selective audit reliability | IPW does not cover unknown real inclusion mechanisms |
| Section 6.5 Module C | `exp4.modules.module_c.run_module_c` | control summary, parameter recovery, correspondence checks | Main calibration table | Calibration-family controls | Positive recoverability is not structural correspondence |
| Appendix C.4 | `exp4.metrics.action_gaps.compute_action_gap_defect` | same as Definition 4.3 | parameters and metric tables | Exact code-theory formula | Formula must remain the per-round maximum over all action pairs |

The main Exp4 figure and table contain no learner result, regret-transfer bound, delay-mechanism comparison, or proxy-impossibility claim.

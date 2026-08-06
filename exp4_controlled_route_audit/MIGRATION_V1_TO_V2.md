# Exp4 v1 to v2 Migration

V2 schema: `exp4_controlled_route_audit_v2`

| Old field or ID | New field or ID | Reason | Compatibility | Value migration | Formal rerun |
|---|---|---|---|---|---|
| `population_raw_action_gap_defect` | `population_action_gap_defect` | Module A has no raw/calibrated pair | Formula-compatible name only | Regression comparison allowed | Yes |
| `ranking_reversal_rate` | `route_optimal_set_conflict_rate` | The implementation tests optimal-set conflict | Name-compatible only | Regression comparison allowed | Yes |
| none | `pairwise_gap_sign_disagreement_rate` | Separates all-pair sign disagreement | New field | No | Yes |
| `margin_preservation_rate` | `margin_certificate_rate` | It is a sufficient-condition certificate | Name-compatible only | Regression comparison allowed | Yes |
| `sample_raw_action_gap_defect` | `audited_action_gap_defect` | Clarifies the audit estimand | Schema rename | No | Yes |
| `raw_estimation_error` | `audit_estimation_error` | Clarifies estimator error | Schema rename | No | Yes |
| `ambiguity_biased_unweighted` | `ambiguity_selective_unweighted` | Selection is a design, not a value judgment | Machine-ID migration | No | Yes |
| `ambiguity_biased_ipw` | `ambiguity_selective_ipw` | Same as above | Machine-ID migration | No | Yes |
| `shuffled_negative` | `blocked_correspondence_destroyed` | The control destroys same-unit correspondence within folds | Machine-ID migration | No | Yes |
| `affine_positive` | `affine_linked` | Names the frozen correspondence construction | Machine-ID migration | No | Yes |
| `labelled_support_coefficient` | removed | Replaced by interpretable support ratios | None | No | Yes |
| repeated `pair_coverage_rate` | invariant manifest | Pair support is fixed at all 45 pairs | None | No | Yes |
| learner/regret artifacts | appendix/validation only or removed | Exp1 owns learner-consequence and transfer evidence | Not promotion compatible | No | No v2 primary value |

## Values That Cannot Be Migrated

The following require a new v2 run because attribution now uses an arrival-side source signature, independently calibrated kernel bandwidth, and an empirical delay prior:

- proxy route defect;
- proxy-noise contrasts;
- attribution diagnostics;
- all Module B audit outputs;
- all Module C calibration outputs;
- the main figure and paper table.

V1 outputs remain read-only regression and provenance evidence. Promotion rejects every v1 or legacy schema.

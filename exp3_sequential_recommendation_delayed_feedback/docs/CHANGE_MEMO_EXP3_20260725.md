# Exp3 Change Memo — 2026-07-25

- **change_id:** `exp3-score-gap-ranking-rebuild-20260725`
- **affected_experiment:** Experiment 3
- **old_rule:** daily score calibration and ranking-regret analysis with partial-label and composite routes in the active paper interface
- **new_rule:** day-by-user-group, two-fold score–gap–ranking recoverability audit with Arrival carrier, Historical mean, and Ridge proxy as the only operational primary routes
- **scientific_reason:** align the logged-data diagnostic with the paper's action-comparison validity main line while preserving the non-causal evidence boundary
- **code_impact:** active pipeline rewritten; naming, support design, bootstrap, outputs, figures, and promotion gates replaced
- **rerun_required:** true
- **existing_outputs_invalidated:** all legacy Exp3 primary figures and tables
- **approved_status:** accepted in project conversation

## Frozen overrides

1. Residual bucket is retained for accounting but excluded from primary candidates.
2. `ranking_regret` is replaced by signed `cross_fitted_ranking_shortfall`.
3. Partial-label routes leave the active Exp3 paper interface.
4. Ridge remains the primary model; GBDT is not activated in this implementation.
5. Full support is 500 events per fold, audit unit, and action.
6. Plotting reads frozen tables only and cannot recompute scientific quantities.

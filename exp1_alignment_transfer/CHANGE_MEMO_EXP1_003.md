# CHANGE MEMO EXP1_003 — Scientific diagnostics migration v1.2 (final-theory contract)

- memo_id: CHANGE_MEMO_EXP1_003
- experiment_id: exp1_alignment_transfer
- approved_status: approved
- patch_type: SCIENTIFIC_DIAGNOSTICS_MIGRATION_PLUS_LINEAGE_REFREEZE
- scientific_rerun_performed: FAST_ONLY
- presentation_rebuild_performed: NO
- exp2_exp4_rerun_performed: NO

## Scope

This memo authorizes the Exp1 v1.2 migration toward the final-theory
contract. It does NOT authorize:

- any change to the primary six-mechanism registry (MECHANISM_ORDER frozen);
- any change to evaluation/calibration seeds, primary K, T, delay families,
  calibration candidate sets, or calibration selection gates;
- any redesign of figures or tables;
- any full run, promotion, paper-candidate replacement, commit, or push.

## Changes

1. `config.py`: CONFIG_VERSION = "1.2"; frozen `TheorySweepConfig`
   (exact_shift_scales, margin_distortion_ratios) added to the canonical
   config payload/hash; paper-facing display name
   "Exact-valid shift" -> "Exact-cardinal-valid shift".
2. `src/metrics.py`: added `ternary_sign`, `pairwise_sign_disagreement` (rho),
   `directed_choice_disagreement` (chi), `complete_conflict_indicator`,
   `structural_conflict_margin` (gamma), `route_conflict_margin` (eta), and
   two-sided `regret_stability_slack`. `ranking_reversal` now validated as
   chi > 0 (same binary event, legacy name retained). No existing quantity
   removed.
3. `src/contracts.py`: new metric IDs and ROUTE_ROUND_COLUMNS extensions.
4. `src/runner.py`: per-round delta/rho/chi/complete-conflict/gamma/eta/
   gap-margin-ratio diagnostics and seed-level summaries; learner behavior
   unchanged.
5. `src/derived.py`: route summary registry extended with the new seed-level
   metrics; no figure redesign.
6. `src/structural_process.py`:
   `generate_exact_valid_shift_path(g_scale=0.6, c_scale=0.1)` parameterized
   with defaults reproducing the primary construction exactly.
7. `src/theory_sweeps.py` (new): exact-cardinal shift amplitude sweep and
   margin/distortion threshold sweep, isolated from the mechanism registry.
8. `targeted.py`: theory sweeps integrated into the non-Cartesian validation
   layer and written to the targeted output directory.
9. `self_check.py`: added scientific gates A-I (validity hierarchy, binary
   legacy consistency, complete conflict, margin bridge, complete-conflict
   margin bound, sharp pathwise regret stability, independent action-sequence
   check, exact-cardinal validity, theory-sweep invariants).
10. `tests/test_scientific_metrics.py` (new): 16 required scientific tests.

## Calibration lineage

This memo authorizes ONE recalibration run, solely as a lineage re-freeze
(`python calibrate.py --force`), AFTER all unit/static checks pass. The
candidate sets, gates, and seeds are unchanged. The new calibration scientific
content must be identical to the prior payload up to machine tolerance;
metadata-only differences (generated_at, code_commit, code_lineage,
config_hash, artifact hashes derived from metadata) are expected and ignored.
If any scientific calibration value changes, STOP and report
HUMAN_DECISION_REQUIRED.

## Verification requirements

- All Exp1 unit tests pass, including the new scientific metric suite.
- Self-check gates A-I pass on the fast run.
- Theory sweeps pass in fast targeted mode.
- Exp1 fast run is for implementation correctness only: no parameter tuning,
  no result optimization.
- No commit and no push is performed.

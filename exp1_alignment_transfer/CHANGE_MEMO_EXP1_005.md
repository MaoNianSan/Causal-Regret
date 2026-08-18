# CHANGE MEMO EXP1_005 — Paper promotion authorization (v1.2 full)

- memo_id: CHANGE_MEMO_EXP1_005
- experiment_id: exp1_alignment_transfer
- approved_status: approved
- patch_type: PAPER_PROMOTION_AUTHORIZATION
- scientific_definition_change: NO
- parameter_change: NO
- full_run_authorized: NO
- paper_promotion_authorized: YES
- presentation_rebuild_authorized: NO
- commit_push_authorized: NO

## Authorization

This memo records the human authorization to promote the current committed
Exp1 v1.2 full scientific result into `outputs/paper_candidate/`. The
authorized promotion source is:

- run_id: `exp1_alignment_transfer:full:2026-08-17T06:28:21.157011+00:00`
- source: `outputs/full` (code_commit `23199c48`)
- technical promotion readiness: PASS (2026-08-18, after reporting-only
  reconciliation; scientific/aggregation/validation provenance unchanged)

Promotion is executed with `python promote.py --run full --force`, replacing
the previous paper-candidate bundle promoted on 2026-08-05 from the earlier
2026-07-26 full run. This is the intended canonical replacement to the
current v1.2 scientific result.

## Explicit exclusions

This memo does NOT authorize:

- any scientific full rerun, parameter tuning, or scientific-definition change;
- figure or presentation redesign beyond the reporting-only reconciliation
  already recorded in `metadata/exp1_provenance_reconciliation.json`;
- CR-EXP-OUTPUT-V1 presentation-layer rebuild or migration;
- canonical documentation replacement, README/REPRODUCE/PAPER_RESULTS updates;
- commit, push, or remote publication;
- changes to Exp2, Exp3, or Exp4.

Each excluded action requires its own separate authorization.

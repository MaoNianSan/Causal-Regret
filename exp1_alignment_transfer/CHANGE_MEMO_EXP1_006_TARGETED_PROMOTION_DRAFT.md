# CHANGE MEMO EXP1_006 (APPROVED) — Targeted manuscript-artifact promotion

> **Approved 2026-09-10 by the human owner. This memo authorizes exactly one
> scope-specific action: the targeted manuscript-artifact promotion below.**
>
> `approved_status: approved`, `targeted_paper_promotion_authorized: YES`.
> The targeted-promotion gate re-reads these fields and re-verifies the snapshot
> bindings below on every run; if any binding value drifts, the gate blocks the
> promotion and this memo must be re-approved.

- memo_id: CHANGE_MEMO_EXP1_006
- experiment_id: exp1_alignment_transfer
- patch_type: TARGETED_PAPER_PROMOTION_AUTHORIZATION
- approved_status: approved
- approved_at: 2026-09-10
- approved_via: Causal_Regret_Exp1_Targeted_Promotion_Authorization_Execution_20260910.md
- paper_promotion_authorized: NO
- targeted_paper_promotion_authorized: YES
- authorized_promotion_scope: targeted_extension

## Snapshot binding

These values are repeated verbatim so that approval binds this exact accepted
snapshot and nothing else. If any of them changes, the memo goes stale and the
gate blocks the promotion again.

- authorized_source_run_id: exp1_alignment_transfer:full:2026-08-17T06:28:21.157011+00:00
- authorized_scientific_generation_hash: d2d2f3c999c070c91e450bc39f0a1f8a0e77574dcabcbf21a9382a4d04a28922
- authorized_validation_hash: e5604c77e3a3640f5facdc7d3161839c2d8260e358e8aed0e075db55cebc8409
- authorized_targeted_validation_report_sha256: 6a0bf750ffd1d5b85960c6bfdf0978f448b006b2db1384afe3bcd4d2007eeaf5
- authorized_cancellation_invariants_sha256: 1514a6e1c7f48c9da0a2ab439f220964397b7f12f7ba530a4999a4c62bbb4834

## What this approval authorizes

Exactly one thing: `python promote_targeted.py` copying the allowlist in
`promote_targeted.TARGETED_ALLOWLIST` from `outputs/full` into the existing
`outputs/paper_candidate` bundle, with governance fields rewritten in the
destination copies only.

- scientific_definition_change: NO
- parameter_change: NO
- primary_full_rerun: NO
- primary_candidate_replacement: NO
- targeted_only_copy_and_flag_transformation: YES
- publication_rebuild_separately_controlled: YES
- commit_push_separately_controlled: YES

## Why the earlier authorization does not carry over

`CHANGE_MEMO_EXP1_005` authorized the **primary** v1.2 promotion executed on
2026-08-18. It is approved and still valid for that primary snapshot, but it
declares no promotion scope and no artifact-hash binding, and it predates the
accepted 2026-09-10 cancellation / horizon-route / stability-utilization
extension. It therefore cannot authorize this targeted promotion, and
`promote_targeted.promotion_authorization()` reports it as
`STALE_PRIMARY_PROMOTION_MEMO_DOES_NOT_AUTHORIZE_TARGETED_EXTENSION` with
`STALE_AUTHORIZATION_REUSE = BLOCKED`.

## Exclusions

This memo does not authorize, under any reading:

- any scientific rerun, recalibration, estimator, metric, seed, or DGP change;
- promotion of the full-run sources themselves (`outputs/full/**` stays
  `paper_result = false`);
- rebuilding or replacing `outputs/paper_candidate/` through the generic
  `promote.py` path;
- editing manuscript LaTeX;
- publication-bundle rebuild under publication/CR-EXP-OUTPUT-V1/.
- commit and push of the promotion result, which the 2026-09-10 execution
  instruction controls separately from this memo.

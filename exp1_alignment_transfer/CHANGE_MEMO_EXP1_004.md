# CHANGE MEMO EXP1_004 - Formal output regeneration authorization

- memo_id: CHANGE_MEMO_EXP1_004
- experiment_id: exp1_alignment_transfer
- approved_status: approved
- patch_type: FORMAL_OUTPUT_REGENERATION
- scientific_definition_change: NO
- parameter_change: NO
- full_run_authorized: YES
- targeted_full_authorized: YES
- presentation_rebuild_authorized: NO
- paper_promotion_authorized: NO

## Authorization

This memo authorizes ONE formal Exp1 v1.2 full scientific rerun, the matching
full self-check, and targeted full theorem sweeps. The execution must use the
committed scientific definitions, seeds, parameter grids, calibration
candidate sets, and selection rules without modification.

This memo also authorizes ONE additional calibration lineage re-freeze only
if the current committed source lineage requires it. Any re-freeze must retain
exact scientific-payload identity after excluding metadata-only fields such as
generation time, code commit or lineage, configuration hashes, and artifact
hashes whose differences follow only from metadata.

## Explicit exclusions

This memo does NOT authorize:

- parameter tuning or result-dependent changes;
- scientific-definition changes;
- figure or presentation redesign;
- overwriting `outputs/paper_candidate/`;
- paper promotion;
- canonical documentation replacement;
- changes to Exp2 or Exp3 scientific code.

If calibration scientific content changes, or any full-run scientific or
provenance gate fails, execution must stop for human review.

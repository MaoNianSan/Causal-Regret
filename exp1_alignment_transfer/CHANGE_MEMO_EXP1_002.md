# CHANGE MEMO EXP1_002 — Presentation-only patch (figures, terminology, repo hygiene)

- memo_id: CHANGE_MEMO_EXP1_002
- experiment_id: exp1_alignment_transfer
- approved_status: approved
- patch_type: PRESENTATION_AND_REPOSITORY_HYGIENE_PATCH
- scientific_rerun_performed: NO
- presentation_rebuild_performed: YES
- exp2_exp4_rerun_performed: NO

## Scope

This memo authorizes a presentation-only patch. It does **not** authorize any
scientific rerun:

- No recalibration (`calibrate.py --force` is forbidden).
- No `main.py fast/full` rerun.
- No targeted-suite rerun.
- No seed, DGP, metric, learner, delay, or config change.
- No Exp2/Exp3/Exp4 rerun.

## Changes

1. `plot_main.py`: Panel (a) now draws two separate right-aligned auxiliary
   columns, `Mean delay` (1 decimal) and `Conflict rate` (route-optimal
   conflict rate, 2 decimals), at fixed axes-fraction x positions so the
   headers and numeric rows no longer overlap. Figure metadata now records
   distinct `scientific_source_lineage` / `presentation_source_lineage`.
2. `plot_appendix.py`: publication-facing terminology normalized
   (`Conflict margin` replaces `Reversal margin`, `Margin-separated conflicts`
   replaces `Margin-separated reversals`); mechanism titles use canonical
   `DISPLAY_NAMES`; figure metadata records distinct lineages.
3. `src/derived.py`: display-only strings normalized (`.tex` table header
   `Conflict rate` replaces `Reversal rate`; figure-data metadata panel
   description updated). No scientific column, value, or bootstrap changes.
4. `.gitignore`: fast/full/dev/tmp outputs, caches, logs, editor/OS temporaries
   and transient status JSONs are ignored; the authoritative
   `outputs/paper_candidate/` is whitelisted and tracked.
5. `README.md`: patch-relevant sections updated.
6. Transient `status/*_status.json` files removed from Git tracking
   (precise `git rm --cached`; files remain on disk).
7. New `tests/` unit tests for header non-overlap, no mixed-scale heatmaps,
   gitignore policy, lineage separation, and frozen-scientific hash invariance.

## Verification requirements

- All 20 frozen scientific artifact SHA-256 hashes recorded in
  `status/EXP1_V2_FROZEN_SCIENTIFIC_ARTIFACTS.json` remain byte-identical.
- `outputs/paper_candidate/` is re-promoted from the existing full artifacts.
- No commit and no push is performed by the patch itself.

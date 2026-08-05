# Exp1 V2 Presentation Patch Report

- patch_type: `PRESENTATION_AND_REPOSITORY_HYGIENE_PATCH`
- branch: `main`
- base_commit: `f75064d9abf1f499e6aa84a794f8971dd407e93f`

## Rerun decision

```text
SCIENTIFIC_RERUN_PERFORMED = NO
PRESENTATION_REBUILD_PERFORMED = YES
EXP2_EXP4_RERUN_PERFORMED = NO
```

## Fixes

1. **Main figure Panel (a) header fix (PASS)**: the combined `delay X; rev. Y`
   row annotation was replaced by two separate right-aligned columns with the
   fixed display names `Mean delay` (1 decimal) and `Conflict rate`
   (route-optimal conflict rate, 2 decimals) at independent axes-fraction x
   positions. Headers and numeric rows are aligned per column and verified
   non-overlapping at render time (`test_headers_do_not_overlap`, 10/10).
2. **Learner-binding diagnostics scale fix**: N/A. `fig_exp1_learner_binding_diagnostics`
   does not exist in this codebase, and no shared-scale heatmap is drawn by any
   figure source (`test_no_heatmap_shared_colorbar_in_figure_sources`).
3. **Route-map staleness scale fix**: N/A. `fig_exp1_route_map_staleness` does not
   exist in this codebase; rates and lags are never shown on a shared color scale.
4. **Terminology normalization (PASS)**: publication-facing displays use
   `Conflict rate` / `Conflict margin` instead of `Reversal rate` / `Reversal margin`;
   `rev.` abbreviation removed; mechanism titles use canonical `DISPLAY_NAMES`;
   `.tex` table header updated.
5. **Lineage**: `scientific_source_lineage` unchanged (`tree:7821dc5d...`);
   `presentation_source_lineage` updated to `presentation:5ce3cadb...`.
6. **Repo hygiene**: `.gitignore` whitelists `outputs/paper_candidate/` and ignores
   fast/full/dev/tmp outputs, caches, logs, editor/OS temporaries and transient
   status JSONs; 8 transient status files untracked via precise `git rm --cached`.

## Scientific hash invariance

All 20 frozen scientific artifacts recorded in
`status/EXP1_V2_FROZEN_SCIENTIFIC_ARTIFACTS.json` are byte-identical after the patch.

## Candidate

- candidate: `outputs/paper_candidate/` (run_tier=paper, paper_result=true)
- PNG sha256: `fdf6920f9d8e528507d5898fb72823539c49a340cd3aaf1506de09c19a88612e`
- PDF sha256: `d983c16ee3215dd7a3f039b52b379629eea58889eaa6eec375b21046917da01c`
- promotion manifest sha256: `952429f51b89ca2547024f2a820332bed0eef8760eb9b99b8ec9d58ad67b6e9d`

## Tests

- `python -m unittest discover -s tests -p 'test_*.py' -v` -> 10/10 OK
- `python -m compileall -q ...` -> exit 0
- `git diff --check` -> exit 0 (benign LF/CRLF warning only)
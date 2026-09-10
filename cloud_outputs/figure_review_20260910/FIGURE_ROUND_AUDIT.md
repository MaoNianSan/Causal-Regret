# Figure Round Audit — CR-EXP-OUTPUT-V1 (preview only)

- Date: 2026-09-10
- Spec: `CR-EXP-OUTPUT-V1`
- Mode: `preview` (writes went outside the repository)
- Repository HEAD: `b1a7775b506c6c290b3d2368e657a8518d06c558`
- `origin/main`: `b1a7775b506c6c290b3d2368e657a8518d06c558` (unchanged, no fetch drift)
- Review root: `D:\research\causalregret\experiment\figure_review_20260910`
- Preview root: `...\figure_review_20260910\preview`

## 1. Status

| Gate | Result |
|---|---|
| Engineering gate | PASS (`pytest` 83 passed, `python -m pytest` 83 passed) |
| Presentation gate | PASS (641 checks across 4 experiments, 0 failed) |
| Scientific preservation | PASS (all six frozen source trees byte-identical) |
| Promotion / publication sync / push | NOT EXECUTED |

## 2. What this round changed

Presentation-only code. No scientific generator, estimator, seed, calibration,
route definition, or attribution rule was touched.

| File | Change |
|---|---|
| `presentation/common.py` | Font stack reordered to `["Arial", "Helvetica", "DejaVu Sans", "sans-serif"]`. Arial resolves on this machine either way, so the rendered result is unchanged; this only aligns the stack with the figure skill's portability recommendation. |
| `exp1_alignment_transfer/presentation.py` | (i) Panel (c) Δ readouts moved into a reserved right lane; (ii) all three main panels now share one row axis; (iii) new appendix figure `exp1_appendix_targeted_cancellation_and_utilization`. |
| `exp3_sequential_recommendation_delayed_feedback/presentation.py` | The single `Ridge - Historical` y-tick label moved inside its own panel as an in-axes label. |
| `exp4_controlled_route_audit/exp4/reporting/presentation.py` | Panel (d) recoverability readouts moved into a reserved right lane. |

## 3. Defects found and fixed

All four defects below were confirmed by zooming into the rendered PNGs before
the fix, and re-confirmed after it. Crops are in `audit/crops/` (before) and
`audit/crops_after/` (after).

1. **Exp1 panel (c) — Δ column covered data.** `Δ 0.067` and `Δ 0.071` were
   drawn on top of the arrival-clock markers of their own rows. Fixed by
   confining the data to `1 - 0.27` of the panel width, so the Δ column always
   has its own lane.
2. **Exp1 panel (c) — legend covered by data.** The `Zero delay` row's
   source-round marker landed on the legend entry `Arrival-clock`. Fixed by
   giving all three panels a single shared row axis with headroom above the top
   row (this also aligns the six mechanisms across panels, which the previous
   per-panel `ylim` values did not).
3. **Exp3 bottom-right panel — label crossed into the neighbouring panel.** The
   `Ridge - Historical` y-tick label reached left across the column gap and sat
   on the `Sign agreement` panel's historical-mean marker. Fixed by moving the
   contrast identity inside its own panel, above the single contrast line.
4. **Exp4 panel (d) — value covered its own marker.** `0.260` was drawn on top
   of the correspondence-destroyed raw-discrepancy marker. Fixed with the same
   reserved-lane treatment as Exp1 panel (c).

## 4. New appendix figure

`exp1_appendix_targeted_cancellation_and_utilization` (appendix only,
`paper_result=false`), rendered from two frozen sources:

- `exp1_alignment_transfer/outputs/full/targeted/exp1_targeted_cancellation_summary.csv`
- `exp1_alignment_transfer/outputs/full/derived/exp1_regret_stability_utilization_summary.csv`

Panels: (a) absolute action-wise level error across the targeted cancellation
grid; (b) mean action-gap defect χ across the same grid; (c) realized stability
utilization on the arrival-assigned route.

The two zero-alignment-budget mechanisms (`zero_delay`, `exact_valid_shift`)
carry **no marker**: they are typed in words as `undefined (zero alignment
budget)`. NaN was never turned into a zero. The targeted sweep is not merged
into the main Exp1 estimand contract and is not inserted into the main figure.

## 5. Programmatic figure QA

Per experiment, all recorded layout gates passed on the real Agg canvas:
`canvas_containment`, `legend_inside_canvas`, `title_inside_canvas`,
`axis_label_inside_canvas`, `cross_panel_title_collision`,
`legend_xlabel_clearance`, `no_long_legend_text`, `no_internal_ids_in_labels`,
`exp1_mean_delay_vs_title`. Plus per-bundle checks: PDF/SVG/PNG all render
non-empty, vector SVG keeps live text, long-form schema complete, source hashes
recorded, three graphic hashes recorded, `paper_result` contract false.

| Experiment | Checks | Failed |
|---|---|---|
| Exp1 | 168 | 0 |
| Exp2 | 150 | 0 |
| Exp3 | 170 | 0 |
| Exp4 | 153 | 0 |

## 6. Candidate vs published bundle

| Experiment | PNG changed | PDF changed | SVG changed |
|---|---|---|---|
| Exp1 | yes | yes | yes |
| Exp2 | **no** | yes | yes |
| Exp3 | yes | yes | yes |
| Exp4 | yes | yes | yes |

Exp2's PNG is byte-identical to the published bundle: no presentation change was
made to Exp2 and the font-stack edit did not alter rendering. Its PDF/SVG differ
only through container metadata (creation timestamps). Exp2's figures are
therefore unchanged, not silently re-styled.

## 7. Scientific preservation

Every frozen scientific source tree hashes identically before and after the
round (`audit/source_hashes_baseline.json` vs `audit/source_hashes_after.json`):

| Tree | Files | Tree SHA-256 (before = after) |
|---|---|---|
| Exp1 preview source | 62 | `e5a31bb76087195821d4657ede9d9f9c1bb62a3d6b136eb4b52d64f93fdd4606` |
| Exp1 publication source | 50 | `6de159ade3810c26945f3bd770c7e4856ebf36b479ec12ac09268b7a1053e252` |
| Exp2 publication source | 40 | `96d853ed88745cf523e0ddf83a071816bbbc0d80520e5bf7d0b301e77de922f7` |
| Exp3 publication source | 43 | `5efa66f80552578ac790faaa0e4c2e1f9992c4917c1d692aad629edb676b7235` |
| Exp4 publication source | 2203 | `53bc136396846450017ac8ec721c434f0054b46d76b5dacd5b71d6e9c4a77e85` |
| Publication bundle | 156 | `9aae989a0d12c16dac773ae8d54fdabdd92e3385d44d27e07758855b74101da1` |

## 8. Distinct issues found but NOT fixed (they are outside this session's authority)

1. **Clean-checkout hash failures (cross-platform fragility).** In a fresh
   checkout at `HEAD`, `pytest exp1_alignment_transfer/tests -q` fails two
   frozen-hash tests (`test_primary_paper_candidate_scientific_hashes_unchanged`
   and `test_presentation_rebuild_does_not_touch_scientific_artifacts`) because
   `seed_metrics/exp1_learner_seed_metrics.csv` checks out with LF endings
   (321,171 bytes) while the frozen hash constant in the test corresponds to the
   CRLF working-tree copy produced by a local Windows run (321,532 bytes). The
   user's working tree keeps the CRLF copy, which is why the suite passes there.
   This is a pre-existing portability issue in the repository, unrelated to the
   figure round, and it is reported rather than changed.
2. **The `exp1_alignment_transfer/presentation.py` import-shadowing guard was
   already present as uncommitted work** when this session started (written
   earlier the same day, `+20` lines). It is preserved verbatim, not authored or
   reverted here. Without it, `python -m pytest exp1_alignment_transfer/tests -q`
   fails at `HEAD` with `ModuleNotFoundError: No module named
   'presentation.common'; 'presentation' is not a package`.
3. **Exp4 panels (b) and (c) draw three audit designs with no legend**, so the
   series cannot be mapped from the panel alone, and several near-zero series
   overlap. Both are honest representations of the frozen values; whether to add
   a legend or separate the overlapping markers is a scientific-presentation
   judgement left to the human reviewer.

## 9. Visual review status

`VISUAL_REVIEW_STATUS = REQUIRES_HUMAN_OR_VISION_MODEL`.

Programmatic gates pass, but no panel is called visually approved on the basis
of programmatic gates alone. `figure_review_sheet_old_vs_new.png` shows the
published bundle and the candidate side by side for all four main figures.

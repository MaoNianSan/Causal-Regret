# Figure review / manuscript handoff snapshot — 2026-09-10

> **This directory is a presentation/review snapshot.
> It is not the scientific source of truth.
> Canonical experiment results remain in the experiment-specific paths.**

This snapshot holds the latest figure-review round outputs so that cloud
readers can review figures and handoff documents without access to the local
machine. Scientific authority is unchanged:

| Experiment | Canonical source of truth |
| --- | --- |
| Exp1 | `exp1_alignment_transfer/outputs/paper_candidate/` (primary); `outputs/full/` (accepted targeted diagnostics, NOT promoted) |
| Exp2 | `exp2_real_delayed_conversion_logs/outputs/paper/exp2-full-20260807T111616+0800/` |
| Exp3 | `exp3_sequential_recommendation_delayed_feedback/outputs/exp3-full-20260807T072340Z/` |
| Exp4 | `exp4_controlled_route_audit/outputs/runs/full_20260817T071019Z_7d7146b7/` |

## Contents

| File | Role |
| --- | --- |
| `FIGURE_ROUND_AUDIT.md` | Human-readable figure round audit |
| `figure_round_audit.json` | Machine-readable figure round audit |
| `figure_review_sheet_old_vs_new.png` | Old-vs-new review sheet image |
| `EXP1_EXP4_MANUSCRIPT_HANDOFF_20260910.md` | Manuscript handoff document |
| `candidate_main_figures/{pdf,png,svg}/` | Candidate main figures (Exp1–Exp4) in three formats |
| `audit/source_hashes_baseline.json` | Source-hash audit (baseline) |
| `audit/source_hashes_after.json` | Source-hash audit (after) |
| `audit/validation_preview_after.json` | Preview validation report (after) |

## What was intentionally not copied

- `preview/` duplicated preview trees (redundant copies of canonical outputs);
- temporary crop images and the helper scripts that created them;
- external `figures4papers` demo scripts;
- `validation_preview_before.json` (kept only the "after" state).

## Disclaimer

Files here are a **non-authoritative** copy of review-stage material. Any
discrepancy between this snapshot and the canonical experiment paths is
resolved in favor of the canonical paths listed above.

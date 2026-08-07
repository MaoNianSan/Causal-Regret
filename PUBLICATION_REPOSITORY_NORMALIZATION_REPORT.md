# Publication Repository Normalization Report

Date: 2026-08-07
Scope: Exp1–Exp4 normalization from a development repository to a
paper-facing reproducibility repository. No scientific redesign, no full
rerun.

---

## A. Local retention

Per-experiment local state after normalization. Raw inputs and the latest
valid run are retained on the local machine; only superseded history was
removed.

### Experiment 1 (`exp1_alignment_transfer/`)
- Retained input: none (controlled simulator; no external dataset).
- Retained calibration: `calibration/` (frozen calibration artifacts +
  manifest).
- Retained latest run: `outputs/paper_candidate/` (the authoritative,
  validated paper artifact set; `exp1_validation_report.json` reports
  engineering/scientific PASS).
- Retained provenance: `outputs/paper_candidate/metadata/artifact_manifest.json`
  (hash records corrected to match the actual files — see B), `exp1_promotion_manifest.json`,
  `CHANGE_MEMO_EXP1_002.md` (required by the promotion gate).
- Deleted: `status/EXP1_V2_*` development-history reports (8 files).
- Transient `status/*_status.json` files remain on disk (git-ignored).

### Experiment 2 (`exp2_real_delayed_conversion_logs/`)
- Retained input (local only, git-ignored): `inputs/criteo_attribution_dataset.tsv.gz`,
  `inputs/pcb_dataset_final.tsv`, `inputs/synthetic_fixture.tsv`,
  `inputs/Experiments.ipynb`.
- Retained latest run: `outputs/exp2-full-20260807T111616+0800/` (latest
  formal full run) and `outputs/paper/` (promoted curated paper output).
- Deleted: none locally (the earlier cohort-check run was already gone).

### Experiment 3 (`exp3_sequential_recommendation_delayed_feedback/`)
- Retained input (local only, git-ignored): `inputs/KuaiRand-1K.tar.gz`,
  `inputs/KuaiRand-1K/`, `inputs/_fast_fixture/`.
- Retained latest run: `outputs/exp3-full-20260807T072340Z/` (canonical full
  run, engineering/scientific PASS, promoted).
- Deleted local run: `outputs/exp3-fast-20260807T071149Z` (real-data fast
  run, superseded by the same-day full run; the full run is self-contained
  and does not depend on it).
- New: `paper_candidate/` (curated paper artifact set with `manifest.json`).

### Experiment 4 (`exp4_controlled_route_audit/`)
- Retained input: none (controlled simulator; `input/.gitkeep` only).
- Retained latest run: `outputs/runs/full_20260807T045219Z_7eeb2a31/`
  (canonical full v2 run, ~990 MB, kept local; results-only subset is
  tracked).
- Deleted: `MIGRATION_V1_TO_V2.md` (pure migration history; the README fully
  describes the current v2 design).

---

## B. GitHub cleanup

### Deleted tracked files (development history)
- `docs/CLEANUP_REFERENCE_CHECK.md`
- `docs/DOCUMENTATION_CLEANUP_PRE_AUDIT.md`
- `docs/EXP2_EXP4_RUN_INSTRUCTIONS.md`
- `docs/EXPERIMENT_DOCUMENTATION_INVENTORY.csv`
- `docs/REPOSITORY_ARTIFACT_AND_CLEANUP_POLICY.md`
- `docs/REPOSITORY_CLEANUP_HISTORY.md`
- `docs/REPOSITORY_EXP124_PRE_CLEANUP_AUDIT.md`
- `docs/REPOSITORY_EXP124_PRE_CLEANUP_FILES.csv` (1.25 MB inventory)
- `exp1_alignment_transfer/status/EXP1_V2_CHANGE_MEMO.md`
- `exp1_alignment_transfer/status/EXP1_V2_CLEANUP_MANIFEST.csv`
- `exp1_alignment_transfer/status/EXP1_V2_FILE_CHANGE_SUMMARY.csv`
- `exp1_alignment_transfer/status/EXP1_V2_FROZEN_SCIENTIFIC_ARTIFACTS.json`
- `exp1_alignment_transfer/status/EXP1_V2_GIT_SYNC_READINESS.json`
- `exp1_alignment_transfer/status/EXP1_V2_PRESENTATION_PATCH_BASELINE.json`
- `exp1_alignment_transfer/status/EXP1_V2_PRESENTATION_PATCH_REPORT.json`
- `exp1_alignment_transfer/status/EXP1_V2_RERUN_DECISION.md`
- `exp2_real_delayed_conversion_logs/inputs/README_local_data.md`
- `exp3_sequential_recommendation_delayed_feedback/docs/EXP3_SCHEMA_MIGRATION.md`
- `exp3_sequential_recommendation_delayed_feedback/inputs/README_local_data.md`
- `exp4_controlled_route_audit/MIGRATION_V1_TO_V2.md`
- Moved: `ipy/github_overview.ipynb` → `notebooks/overview.ipynb`

Every deletion was preceded by a reference check (code, README, config,
tests, manifests). None of the deleted files had runtime or scientific
provenance dependencies:

- `CHANGE_MEMO_EXP1_002.md` was **retained** because `promote.py` and
  `self_check.py` read `CHANGE_MEMO_EXP1_*.md` for the promotion gate.
- `exp4/reports/EXP4_V2_IMPLEMENTATION_STATUS.md` was **retained** because
  `main.py status` reads/writes it.

### Retained scientific files
All current scientific source code, configuration, tests, calibration
artifacts, and current manifests for Exp1–Exp4 are unchanged and remain
tracked.

### Retained publication artifacts (GitHub)
- Exp1: `outputs/paper_candidate/` (figures, tables, source data, checks,
  metadata, manuscript values).
- Exp2: `outputs/paper/exp2-full-20260807T111616+0800/` (figures, tables,
  derived data, audit checks, run manifest).
- Exp3: `paper_candidate/` (main + appendix figures, source data, paper
  tables, `manifest.json`).
- Exp4: `outputs/runs/full_20260807T045219Z_7eeb2a31/` (figures, tables,
  checks, derived summaries, run report).

### Provenance correction (metadata only)
`exp1_alignment_transfer/outputs/paper_candidate/metadata/artifact_manifest.json`
recorded stale hashes (they had been copied from the frozen full-run list,
including four `raw/*.parquet` entries that are not part of the paper
candidate). The manifest was regenerated from the actual paper-candidate
files (39 artifacts), and a `corrected_at` + `note` field documents the
correction. No scientific file was modified; `exp1_promotion_manifest.json`
(which already recorded the true hashes) confirms the files are unchanged.

---

## C. Added publication interfaces

- `README.md` — rewritten as a publication landing page (research question,
  overview, experiments, repository structure, quick start, paper results,
  data, compute, citation, license).
- `REPRODUCE.md` — 10-section reproduction guide (environment, data prep,
  smoke test, per-experiment commands, paper figures/tables, expected
  outputs, compute). All commands run from the repository root with relative
  paths; no personal paths, cleanup history, or git-sync anecdotes.
- `DATA.md` — data provenance for all four experiments (sources, citations,
  licenses, expected files, placement, fields used, split, redistribution
  policy).
- `docs/PAPER_RESULTS.md` — manuscript-item to repository-artifact map
  (experiment, scientific question, command, canonical run, source data,
  final artifact) for every paper figure/table; numbering not yet frozen.
- `CITATION.cff` — citation metadata (title, repository URL, version); DOI,
  journal, and final year intentionally omitted pending publication; author
  list placeholder.
- `environment.yml` — frozen environment recorded from the actual working
  environment (Python 3.11.6) used for the reported results.
- `LICENSE_SELECTION_REQUIRED.md` — documents that license selection is an
  author decision; no license was silently chosen.
- `reproduce.py` — thin forwarding wrapper (`smoke`, `full --exp N`,
  `--dry-run`); it does not reimplement any experiment logic.
- `exp3_sequential_recommendation_delayed_feedback/paper_candidate/` — new
  Exp3 paper-facing artifact set with `manifest.json` (run id, commit,
  config/design/code hashes, self-check status, contents).
- `notebooks/overview.ipynb` — moved publication overview notebook (relative
  paths still resolve correctly after the move).
- `.gitignore` / per-experiment `.gitignore` — removed stale
  `README_local_data.md` whitelists, moved the notebook whitelist from
  `ipy/` to `notebooks/`, whitelisted `LICENSE_SELECTION_REQUIRED.md`; raw
  datasets remain untracked.
- Exp2/Exp3 `inputs/README.md` — converged to a single formal input document
  (dataset, source, citation, access/license, expected file/directory,
  fields used, primary 7-day / 30-day robustness windows, redistribution
  policy).

---

## D. Verification

| Check | Result |
|---|---|
| `python -m compileall` (all four experiments + `reproduce.py`) | PASS |
| Exp1 tests (`pytest exp1_alignment_transfer/tests`) | 9 passed, 1 skipped |
| Exp2 tests (`pytest exp2_real_delayed_conversion_logs/tests`) | 26 passed |
| Exp3 tests (`pytest exp3_sequential_recommendation_delayed_feedback/tests`) | 57 passed |
| Exp4 tests (`pytest exp4_controlled_route_audit/tests`) | 77 passed, 1 skipped |
| Exp3 synthetic-fixture fast run + self-check | PASS (pipeline + independent self-check PASS) |
| Exp4 fast smoke run | PASS (engineering + scientific PASS) |
| `python reproduce.py smoke --dry-run` / `full --exp N --dry-run` | OK (correct per-experiment commands) |
| `git diff --check` | PASS (EOL-normalization warnings only) |
| Post-deletion reference scan | No stale references to deleted files/paths/absolute paths; `legacy`/`v1`/`deprecated` hits are legitimate compatibility logic and were not touched |

Note: Exp1's full self-check requires the local `outputs/full/raw/*.parquet`
(not retained in this repository); the frozen-hash invariant is instead
verified by the updated unit test against the tracked paper-candidate
artifact manifest.

---

## E. Scientific invariance

```
SCIENTIFIC_LOGIC_CHANGED      = NO
SCIENTIFIC_PARAMETERS_CHANGED = NO
SCIENTIFIC_RESULTS_CHANGED    = NO
FULL_RERUN_EXECUTED           = NO
INPUT_DATA_DELETED            = NO
LATEST_VALID_RUN_RETAINED     = YES
```

Only two test files were adapted, both without changing any scientific
implementation:

1. `exp1_alignment_transfer/tests/test_presentation_hygiene.py` — the
   frozen-hash check now verifies the tracked paper-candidate artifact
   manifest instead of the removed `status/EXP1_V2_FROZEN_SCIENTIFIC_ARTIFACTS.json`
   (which referenced the not-retained `outputs/full/` tree).
2. `exp4_controlled_route_audit/tests/regression/test_v1_migration.py` — the
   v1-baseline assertion skips when the removed v1 run directory is absent.

Smoke runs executed (Exp3 synthetic fixture fast, Exp4 fast) are
engineering-tier verification runs; they were removed after verification and
are not paper results.

---

## F. Remaining manual decisions

- **LICENSE**: choose and add a `LICENSE` file (see
  `LICENSE_SELECTION_REQUIRED.md`).
- **Manuscript figure/table numbering**: final numbers will be applied to
  `docs/PAPER_RESULTS.md` at submission.
- **Paper DOI / journal / final publication year**: add to `CITATION.cff`.
- **CITATION.cff authors**: fill in the author list.
- **GitHub release / tag**: create once the paper is public.
- **Double-blind anonymization**: strip identifying metadata if the venue
  requires it.
- **Exp1 `CHANGE_MEMO_EXP1_002.md`**: retained as an approved scientific
  record; it contains one historical reference to the removed
  `status/EXP1_V2_FROZEN_SCIENTIFIC_ARTIFACTS.json` (accurate as a record of
  the time).

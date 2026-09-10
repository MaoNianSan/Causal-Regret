# Cloud output exclusions

> Companion to [`CLOUD_OUTPUT_INDEX.md`](CLOUD_OUTPUT_INDEX.md). Generated
> 2026-09-10. This report lists important local artifacts that were
> **intentionally NOT pushed** in the cloud-readability synchronization round,
> so future cloud agents do not assume they were forgotten.

## raw / licensed data

| Location | Why excluded | Where the summarized output lives on GitHub instead |
| --- | --- | --- |
| Exp2 `inputs/*.tsv`, `*.gz` (Criteo delayed-conversion log) | Licensed external dataset, not redistributable | `exp2_real_delayed_conversion_logs/outputs/paper/exp2-full-20260807T111616+0800/` (derived summaries and tables) |
| Exp3 raw/source KuaiRand logs | Licensed external dataset, not redistributable | `exp3_sequential_recommendation_delayed_feedback/outputs/exp3-full-20260807T072340Z/` (derived summaries and tables) |
| Exp1 `outputs/full/raw/` (4 parquet simulations, ~305 MB) | Row-level simulation intermediates; regenerable | `exp1_alignment_transfer/outputs/full/derived/`, `.../targeted/`, `.../seed_metrics/` |
| Exp4 run `raw/` subtrees | Row-level simulation intermediates; regenerable | `exp4_controlled_route_audit/outputs/runs/full_20260817T071019Z_7d7146b7/derived/` |

## large intermediates

| Location | Why excluded | Where the summarized output lives on GitHub instead |
| --- | --- | --- |
| Exp3 `outputs/exp3-full-20260807T072340Z/processed/` (≈1.6 GB parquet event tables) | Large row-level intermediates; regenerable from raw logs | `.../derived/*.csv`, `.../tables/*.csv`, `.../checks/*.csv` |

## parquet / binary analytical cache

| Location | Why excluded | Where the summarized output lives on GitHub instead |
| --- | --- | --- |
| Exp1 `outputs/full/seed_metrics/*.parquet` (2 files, ~87 KB each) | Binary cache; CSV twins are published | `exp1_alignment_transfer/outputs/full/seed_metrics/*.csv` |
| Exp3 `derived/*.parquet` (10 files) and `derived/exp3_evaluation_arrays.npz` | Binary analytical cache; CSV twins are published | `.../derived/*.csv`, `.../tables/*.csv` |
| Exp3 `design/exp3_user_assignments.parquet` | Binary design cache | `.../design/*.csv|*.json` |
| Exp4 run `derived/**/*.parquet` | Binary cache (already excluded by project ignore rules) | `.../derived/**/*.csv` |
| Review package preview trees | Duplicated binary preview copies of canonical outputs | `cloud_outputs/figure_review_20260910/candidate_main_figures/` |

## historical development runs

| Location | Why excluded | Where the current canonical output lives on GitHub instead |
| --- | --- | --- |
| Exp1 `outputs/fast/`, `outputs/dev*/` | Transient development runs | `exp1_alignment_transfer/outputs/paper_candidate/` and `outputs/full/` |
| Exp2 non-paper runs (`outputs/exp2-fast-*`, `exp2-middle-*`, `cohort-check-*`, `refactor_audit/`) | Development/audit scratch, not canonical | `exp2_real_delayed_conversion_logs/outputs/paper/exp2-full-20260807T111616+0800/` |
| Exp4 `fast_*`, `middle_*` runs, older `full_20260807T045219Z_*` run | Non-canonical development runs | `exp4_controlled_route_audit/outputs/runs/full_20260817T071019Z_7d7146b7/` |
| Exp3 `legacy/` subtree | Empty/legacy layout | `outputs/exp3-full-20260807T072340Z/` |

## duplicated preview artifacts

| Location | Why excluded | Where the summarized output lives on GitHub instead |
| --- | --- | --- |
| `figure_review_20260910/preview/**` (full duplicated preview trees) | Redundant copies of canonical outputs | canonical per-experiment paths + `cloud_outputs/figure_review_20260910/candidate_main_figures/` |
| `figure_review_20260910/audit/crops*`, `crops_after/` | Temporary crop images for review | `figure_review_sheet_old_vs_new.png` |
| `figure_review_20260910/audit/figures4papers_reference/` | External demo scripts | not relevant to this repository |
| `figure_review_20260910/audit/*.py` helper scripts | One-off helper code for the review round | audit outputs are in `cloud_outputs/figure_review_20260910/` |

## temporary audit files

| Location | Why excluded | Where the summarized output lives on GitHub instead |
| --- | --- | --- |
| `audit/validation_preview_before.json` | Pre-change state; only the "after" state is indexed | `cloud_outputs/figure_review_20260910/audit/validation_preview_after.json` |

## local environment / cache

| Location | Why excluded | Where the summarized output lives on GitHub instead |
| --- | --- | --- |
| `.venv/`, `__pycache__/`, `.pytest_cache/` | Local environment and caches | n/a |
| Exp1 `outputs/**/cache/`, `logs/` (local run logs) | Runtime logs without scientific interpretation | validation records under `outputs/full/checks/` |

## notes

- Exp1 `outputs/full/figures/` main-figure files are published as part of the
  accepted full-run bundle (tier `accepted_nonpromoted`); the **promoted**
  Exp1 main figure remains `outputs/paper_candidate/figures/`.
- Exp2/Exp3/Exp4 canonical runs were verified as already/now tracked; no
  canonical file was modified during this synchronization.

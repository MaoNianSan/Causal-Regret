# Exp2 execution guide

## Before running

1. Put the protected input at `inputs/pcb_dataset_final.tsv`.
2. Work from this package root.
3. Do not reuse outputs from older Exp2 packages. This version changes statistical field names, main figure coordinates, appendix structure, and semantic checks.

## Fast run

```powershell
python main.py --mode fast --n-jobs auto
python self_check.py --mode fast
python code_check.py --mode fast
```

For synthetic validation only, use an explicit fixture path so the protected Criteo input is not touched:

```powershell
python tests\generate_synthetic_fixture.py --output inputs\synthetic_fixture.tsv
python main.py --mode fast --input inputs\synthetic_fixture.tsv --n-jobs 1
python tests\check_decision_cell_smoke.py --output-root outputs\fast
```

Review these before deciding on full:

```text
outputs/fast/processed/exp2_conversion_uid_integrity_summary.csv
outputs/fast/summaries/exp2_candidate_set_summary.csv
outputs/fast/summaries/exp2_main_route_divergence_audit.csv
outputs/fast/summaries/exp2_source_route_pairwise_overlap.csv
outputs/fast/summaries/exp2_pairwise_top_k_overlap.csv
outputs/fast/summaries/exp2_em_assignment_diagnostic.csv
outputs/fast/processed/exp2_candidate_window_uid_integrity.csv
outputs/fast/summaries/exp2_route_sensitivity_summary.csv
outputs/fast/checks/exp2_self_check_report.md
```

Stop if any semantic gate fails. In particular, do not run full when decision-cell ambiguity, core source-route divergence, EM nontriviality, action-universe, UID, or window-specific integrity checks fail.

## Full run

```powershell
python main.py --mode full --n-jobs auto
python self_check.py --mode full
python code_check.py --mode full
```

The runner finalizes full figure bundles only after the pre-final semantic self-check passes. `paper_result=true` therefore cannot appear on a failed full run.

## Rerun policy after edits

| Edited component | Minimum required rerun |
|---|---|
| `stats_exp2.py`, `plot_exp2.py`, tables, or self-check | `main.py --mode fast` from the start, because output contracts and figure bundles change together |
| timeline construction, action mapping, route assignment, input parsing, config action/cohort/routes | clean full fast pipeline from `main.py` |
| any empirical full result used in paper | clean full pipeline from `main.py` |

This package has no valid shortcut from an older `stats_exp2.py` output.

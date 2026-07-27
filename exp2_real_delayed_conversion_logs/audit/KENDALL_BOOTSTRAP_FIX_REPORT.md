# Kendall Bootstrap Fix Report

## Decision

Root cause is `MULTIPLE_CAUSES`: confirmed replicate-specific support drift plus fixed-support percentile-bootstrap distribution behavior for the six source-route comparisons. The implementation was modified because the support error was proven by code inspection, exact reconstruction of all saved draws, and the A/B experiment.

## Minimal implementation change

- `metrics.py` freezes stable `decision_cell_id` tuples in `PairwiseMetricState` for all four arrival-anchor and all six source-route comparisons. The full-sample point calculation evaluates the same stored support, leaving its value unchanged.
- `runner.py` explicitly passes those states into bootstrap. Bootstrap cannot infer a new Kendall support from replicate credits.
- `bootstrap.py` aligns UID-resampled credits to the frozen universe, evaluates tau-b on the fixed mask, and records full support, replicate support, frozen status, NaN, constant-vector, and zero-mass diagnostics.
- `validation.py` requires full support = bootstrap minimum = bootstrap maximum for every comparison and stops scientific validation if Kendall NaN fraction exceeds 5%.
- `reporting.py` exposes the frozen-support definition in manuscript tables and reconstructable CSVs.
- `promote.py` updates the paper `self_check.json` and writes `promotion_audit.json`, so paper manifest, self-check, and promotion audit all report `PROMOTED` and `paper_result=true` after a successful promotion.

No cohort, lookback, candidate-window, decision-cell, route, decay, allocation-TV, Top-k, bootstrap unit, repetition, seed, confidence level, or interval-method definition changed.

## Regression evidence

`pytest -q` completed with 15 passing tests. Coverage includes frozen support across replicates, unchanged point tau-b, unchanged allocation TV and Top-k, arrival and pairwise support state coverage, explicit constant/all-zero NaN behavior, support audit fields, worker reproducibility, and promotion consistency.

The fast pipeline run `exp2-fast-20260727T095307+0800` completed with engineering and scientific PASS. All ten comparisons had frozen support with identical full/min/max counts and maximum NaN fraction 0.

The formal full rerun was not completed because the user requested to run it independently. The briefly started run `exp2-full-20260727T095350+0800` is explicitly marked `ABORTED / USER_REQUESTED_STOP`; it is not a result artifact.

## Rerun decision

A bootstrap-chain-only rerun is not authorized. Although input, config, cohort, decision-cell universe, and seed identities are recorded, the old manifest lacks a candidate-mapping hash and a route-credit artifact hash. The required scope is therefore a new full run.

## Current gate status

| Gate | Status |
| --- | --- |
| Code engineering verification | PASS |
| Kendall point estimates unchanged | PASS |
| Allocation TV unchanged | PASS |
| Top-k unchanged | PASS |
| Frozen support implementation | PASS |
| Promotion consistency implementation | PASS |
| Repaired formal full scientific validation | STOP_AND_REVIEW (not run) |
| Repaired paper promotion | NOT_RUN |
| Manuscript ready | false |

Next action: run `python main.py full` from the Experiment 2 project root. After that run passes, promote its new run ID with `python promote.py --run-id <new-run-id>`.

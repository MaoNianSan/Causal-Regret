# Experiment 2: Attribution Sensitivity in Delayed-Conversion Logs

## Overview

This experiment measures **attribution sensitivity** on a fixed
delayed-conversion log using multiple route definitions and support-aware
diagnostics. The scientific boundary is explicit: it is an attribution
sensitivity diagnostic, not an identification of a causally correct
attribution rule, and it does not estimate deployment value, ROI, profit,
uplift, or structural causal regret. The authoritative input/output contract
(route definitions, paper-term ↔ code-identifier mapping, metrics,
uncertainty semantics) is in
[`docs/EXPERIMENT_IO_CONTRACT.md`](../docs/EXPERIMENT_IO_CONTRACT.md).

## Input

- **Data availability**: `DOWNLOAD_REQUIRED` / `NOT_REDISTRIBUTED` — Criteo
  delayed-conversion log; see [`DATA.md`](../DATA.md) and `inputs/README.md`.
- Expected local path: `inputs/pcb_dataset_final.tsv` (derived from
  `criteo_attribution_dataset.tsv.gz`).
- The analysis uses a fixed delayed-conversion log with a frozen decision-cell
  universe, impression denominator, support thresholds, and UID-resampling
  procedure. Primary (7-day) and robustness (30-day) windows are fixed.

## Run

```bash
python -m compileall exp2_real_delayed_conversion_logs
pytest -q exp2_real_delayed_conversion_logs/tests
python exp2_real_delayed_conversion_logs/main.py fast
python exp2_real_delayed_conversion_logs/main.py cohort-check --mode full
python exp2_real_delayed_conversion_logs/main.py full
python exp2_real_delayed_conversion_logs/promote.py --run-id <full_run_id>
```

(From the repository root, as shown.)

## Output

Primary outputs include cohort summaries, comparison tables, ambiguity
diagnostics, figures, and the self-check manifest, written to
`outputs/exp2-full-<UTC timestamp>/`.

## Paper-facing artifacts

- Canonical result: `outputs/paper/exp2-full-20260807T111616+0800/`
  (`paper_result=true`, `paper_promotion_status=PROMOTED`).
- Main figure ID: `figure_exp2_attribution_sensitivity`.
- Publication bundle: `../publication/CR-EXP-OUTPUT-V1/exp2_real_delayed_conversion_logs/`.

## Validation

The package validates cohort support, route diagnostics, and self-check
outputs before any promotion step. Development overrides and legacy-schema
runs are not paper candidates.

## Interpretation boundary

- The ranking score is credited-conversion mass per eligible impression and
  is **not** interpreted as a conversion rate or policy value.
- The resampling interval is a UID-cluster empirical **sensitivity range**
  (2.5%–97.5%), **not** a confidence interval.
- The primary attribution window is fixed at 7 days; any future change to it
  requires a complete Exp2 rerun. Exp2 does not require rerunning Exp1, Exp3,
  or Exp4.

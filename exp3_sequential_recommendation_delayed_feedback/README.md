# Experiment 3: Logged-Supported Ranking Recovery

## Overview

This experiment evaluates **logged-supported ranking recovery** on the frozen
KuaiRand design, with score recovery → reference-pair gap recovery → ranking
recovery as the scientific chain. It is a logged-support diagnostic: it does
not estimate structural causal regret, causal action gaps, off-policy value,
online policy value, deployment performance, or optimal recommendations. The
authoritative input/output contract (route families, paper-term ↔
code-identifier mapping, metrics, uncertainty semantics) is in
[`docs/EXPERIMENT_IO_CONTRACT.md`](../docs/EXPERIMENT_IO_CONTRACT.md).

## Input

- **Data availability**: `DOWNLOAD_REQUIRED` / `NOT_REDISTRIBUTED` — KuaiRand-1K
  logs; see [`DATA.md`](../DATA.md) and `inputs/README.md`.
- Expected local files under `inputs/KuaiRand-1K/data/`:
  `log_standard_4_08_to_4_21_1k.csv`, `log_standard_4_22_to_5_08_1k.csv`,
  `video_features_basic_1k.csv`.
- The frozen design uses a deterministic two-fold user split, support
  thresholds, time bins, and a constructed six-hour post-exposure target. The
  three route families are the arrival carrier, historical mean, and ridge
  proxy.

## Run

```bash
# From the experiment directory (see RUN_THIS_FIRST.txt for the full checklist)
python -m compileall .
pytest -q

# Audit the real split before any run
python main.py audit-inputs

# Fast tier (engineering gate)
python main.py fast --n-jobs 4
python main.py self-check --mode fast --run-id <real_fast_run_id>
python main.py fast --synthetic-fixture --n-jobs 4   # no external data needed

# Formal full run + promotion
python main.py full --n-jobs <N>
python main.py self-check --mode full --run-id <new_full_run_id>
python promote.py --run-id <new_full_run_id>
```

## Output

Canonical outputs include the metric registry, primary route results, paired
ranking contrast, support coverage, gap error distribution, target audit,
ridge history cross-validation summary, and diagnostics tables.

## Paper-facing artifacts

- Canonical result: `paper_candidate/` from the canonical full run
  `exp3-full-20260807T072340Z` (`paper_result=true`).
- Main figure ID: `exp3_main_score_gap_ranking`.
- Publication bundle:
  `../publication/CR-EXP-OUTPUT-V1/exp3_sequential_recommendation_delayed_feedback/`.

## Validation

The independent self-check validates the frozen design, route support, ridge
selection, target audit, and figure-data contract. Fast runs are engineering
gates only and are not paper results.

## Interpretation boundary

- The resampling interval is a user-cluster empirical **sensitivity range**
  (2.5%–97.5%), **not** a confidence interval.
- The experiment remains limited to logged-supported recovery and does not
  claim deployment or causal identification beyond the frozen contract.

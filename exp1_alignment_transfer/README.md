# Experiment 1: Controlled Alignment and Regret Transfer

## Overview

This experiment tests whether **action-gap alignment**, rather than delay
magnitude alone, governs whether route-level optimization can control
structural regret under delayed feedback. The implementation separates two
distinct objects:

- **route-map diagnostic**: simulator-only full-map analysis of route validity
  and regret transfer;
- **learner consequence**: the same contextual Delayed EXP3 learner under
  arrival-clock and source-round scalar-feedback binding.

This is a controlled-simulation experiment. The authoritative input/output
contract (units, mechanisms, config hashes, metrics, uncertainty semantics) is
in [`docs/EXPERIMENT_IO_CONTRACT.md`](../docs/EXPERIMENT_IO_CONTRACT.md).

## Input

- **Data availability**: `AVAILABLE_IN_REPO` — no external raw dataset.
- The frozen simulation settings live in `config.py`; the frozen calibration
  artifacts (delay, misbinding, structural, and context calibration JSON +
  manifest) live in `calibration/`.
- Formal runs require the parquet engine and respect the frozen calibration
  artifacts.

## Run

```bash
python -m pip install -r requirements.txt
python calibrate.py

# Fast tier (engineering gate; not a paper result)
python main.py fast
python self_check.py --run fast
python targeted.py --run fast
python plot_main.py --run fast
python plot_appendix.py --run fast

# Formal full run + promotion
python main.py full
python self_check.py --run full
python targeted.py --run full
python plot_main.py --run full
python plot_appendix.py --run full
python promote.py --run full
```

Selective rebuild of a downstream stage without a scientific rerun uses
`reconcile.py --source-run outputs/full --rebuild {validation,aggregation,
reporting,downstream}` (see `REPRODUCE.md` section D.1).

## Output

Main outputs are written under the run-tier output tree (`outputs/`) and
include raw data, seed metrics, derived tables, figures, checks, metadata,
and manuscript artifacts. The paper candidate is produced from frozen derived
data only.

## Paper-facing artifacts

- Canonical result: `outputs/paper_candidate/` (schema current **v1.2**,
  `paper_result=true`).
- Source full run: `exp1_alignment_transfer:full:2026-08-17T06:28:21.157011+00:00`
  (code_commit `23199c48`).
- Publication bundle: `../publication/CR-EXP-OUTPUT-V1/exp1_alignment_transfer/`
  (main figure ID `fig_exp1_alignment_transfer`).

## Validation

The formal self-check and targeted validation must report `PASS` before any
promotion step. The package hard-fails when required scientific invariants or
calibration checks do not pass. `reconcile.py` is the only supported reuse
interface for an existing run and never reruns the primary scientific full or
changes `raw/` or seed-level scientific artifacts.

## Interpretation boundary

- The experiment is a controlled-simulation diagnostic of route-level
  alignment and structural regret transfer; it does not estimate deployment
  value or real-world policy performance.
- Presentation-only rebuilds do not rerun the scientific experiment.
- Formal full runs remain separate from presentation-only regeneration.

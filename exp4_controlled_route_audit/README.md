# Experiment 4: Recoverability Boundary Diagnostic

## Overview

This experiment studies the **recoverability boundary** of route alignment and
audit reliability under controlled simulation settings. It evaluates whether
route-label retention, source-signature noise, and finite evidence produce
recoverable diagnostics — without claiming causal identification. It is a
recoverability boundary diagnostic: it does not identify a real-world causal
attribution rule, prove proxy impossibility, or treat calibration improvement
as route validity. The authoritative input/output contract (module structure,
metrics, uncertainty semantics, provenance) is in
[`docs/EXPERIMENT_IO_CONTRACT.md`](../docs/EXPERIMENT_IO_CONTRACT.md).

## Input

- **Data availability**: `AVAILABLE_IN_REPO` — no external raw dataset.
- The controlled simulation (state process, delay process, observation proxy,
  calibration) is part of the package under `exp4/simulation/`.
- The design uses frozen route-label rates, source-signature noise levels,
  audit rates, and calibration-fold structure (module A/B/C). Current result
  schema: `exp4_controlled_route_audit_v3`.

## Run

```bash
python -m pip install -r requirements.txt

# Fast / middle / formal full tiers
python main.py fast --n-jobs 4
python main.py middle --n-jobs 8
python main.py full --n-jobs 8

# Downstream stages for a completed run
python main.py validate --run-dir outputs/runs/<run_id>
python main.py aggregate --run-dir outputs/runs/<run_id>
python main.py plot --run-dir outputs/runs/<run_id>
python main.py tables --run-dir outputs/runs/<run_id>
python main.py report --run-dir outputs/runs/<run_id>
python main.py provenance --run-dir outputs/runs/<run_id>
```

Selective rebuild of a downstream stage without a scientific rerun uses
`main.py reconcile --run-dir outputs/runs/<run_id> --rebuild {validation,
aggregation,reporting,downstream}` (see `REPRODUCE.md` section D.4). `main.py
full` refuses to start from a dirty Exp4 worktree or an unresolvable git
commit.

## Output

Outputs are separated into calibration, module A, module B, and module C
results, with figure bundles and tables written from the frozen derived
outputs.

## Paper-facing artifacts

- Canonical result: `outputs/runs/full_20260817T071019Z_7d7146b7/`
  (schema `exp4_controlled_route_audit_v3`, `paper_result=true`,
  `paper_promotion=PASS`, provenance VERIFIED).
- Main figure ID: `fig_exp4_route_alignment_and_audit_reliability`.
- Publication bundle:
  `../publication/CR-EXP-OUTPUT-V1/exp4_controlled_route_audit/`.
- Superseded legacy: `outputs/runs/full_20260807T045219Z_7eeb2a31/` (v2) is
  kept but is no longer canonical. The legacy v2 field
  `population_action_gap_defect` corresponds to the v3 secondary
  `mean_round_max_gap_defect`; it is not a numerical reference target for the
  recomputed primary `D_pair`.

## Validation

The self-check validates scientific invariants and output consistency
(including `panel_a` `D_pair` and legacy v2 exclusion). Promotion is a
separate manual action that accepts only a completed full v3 run that passes
the relevant gates and receives human approval; the current v3 run has
completed that approval. A changed source tree or Git commit alone does not
force a new simulation; only a simulation/configuration/calibration mismatch
or incomplete raw evidence does.

## Interpretation boundary

- Module A's primary discrepancy is the mean pairwise gap discrepancy `D_pair`
  (`mean_pairwise_gap_discrepancy`); its secondary complete-map quantity is
  `A_T/T` (`mean_round_max_gap_defect`). These are distinct quantities and
  must not be reinterpreted as equal.
- All outputs remain recoverability diagnostics rather than policy value
  estimates or route-validity certificates. The experiment does not support
  claims about real-world causal identification or policy validity.

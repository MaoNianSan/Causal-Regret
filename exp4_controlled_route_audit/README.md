# Experiment 4: Recoverability Boundary Diagnostic

## 1. Experiment Objective
This experiment studies the recoverability boundary of route alignment and audit reliability under controlled simulation settings. It evaluates whether route-label retention, source-signature noise, and finite evidence produce recoverable diagnostics without claiming causal identification.

## 2. Scientific Boundary
Experiment 4 is a recoverability boundary diagnostic. It does not identify a real-world causal attribution rule, prove proxy impossibility, or treat calibration improvement as route validity.

## 3. Data and Split
The design uses controlled simulation settings for module A, module B, and module C, with frozen route-label rates, source-signature noise levels, audit rates, and calibration-fold structure. The current result schema is `exp4_controlled_route_audit_v3`.

## 4. Estimand / Metrics
Module A's primary discrepancy is the mean pairwise gap discrepancy, `D_pair` (`mean_pairwise_gap_discrepancy`). Its secondary complete-map quantity is the mean round-max gap defect, `A_T/T` (`mean_round_max_gap_defect`). These are distinct quantities and must not be reinterpreted as equal.

Module B audits the pair-average unit discrepancy. Module C reports pair-average comparison discrepancy before and after out-of-fold calibration. All outputs remain recoverability diagnostics rather than policy value estimates or route-validity certificates.

## 5. Implementation Contract
The pipeline validates source-bound and full-label zero defect, action-pair invariants, positivity, temporal leakage constraints, affine recovery, and the Exp1-Exp4 boundary. The run and figure outputs are generated from frozen derived data and validated by the self-check mechanism.

## 6. Output Artifacts
Outputs are separated into calibration, module A, module B, and module C results, with figure bundles and tables written from the frozen derived outputs.

The current canonical (promoted paper result) is
`outputs/runs/full_20260817T071019Z_7d7146b7/` (result schema
`exp4_controlled_route_audit_v3`, `paper_result=true`, promotion PASS,
provenance VERIFIED). The earlier v2 run
`outputs/runs/full_20260807T045219Z_7eeb2a31/` is kept as a **superseded
legacy** result; it is no longer the canonical or paper-facing result. The
legacy v2 field `population_action_gap_defect` corresponds to the v3 secondary
`mean_round_max_gap_defect`; it is not a numerical reference target for the
recomputed primary `D_pair`.

## 7. Validation and Self-check
The self-check validates scientific invariants and output consistency. Promotion is a separate manual action that accepts only a completed full v3 run that passes the relevant gates and receives human approval; the current v3 run has completed that approval (`paper_promotion=PASS`).

## 8. Running Commands
```powershell
python -m pip install -r requirements.txt
python main.py fast --n-jobs 4
python main.py middle --n-jobs 8
python main.py full --n-jobs 8
```

```powershell
python main.py validate --run-dir outputs/runs/<run_id>
python main.py aggregate --run-dir outputs/runs/<run_id>
python main.py plot --run-dir outputs/runs/<run_id>
python main.py tables --run-dir outputs/runs/<run_id>
python main.py report --run-dir outputs/runs/<run_id>
```

### Selective rebuild without scientific rerun

Use the explicit reconcile command for a verified source run. It audits the
simulation-stage source and scientific-config hashes, calibration identity, raw path
manifests, run lineage, and prior scientific validity before reusing raw
simulation outputs.

```powershell
python main.py reconcile --run-dir outputs/runs/<run_id> --rebuild validation
python main.py reconcile --run-dir outputs/runs/<run_id> --rebuild aggregation
python main.py reconcile --run-dir outputs/runs/<run_id> --rebuild reporting
python main.py reconcile --run-dir outputs/runs/<run_id> --rebuild downstream
```

The command writes `logs/exp4_provenance_reconciliation.json` and preserves
raw simulation data. A different complete source-tree hash or Git commit alone
does not require a new simulation; only a simulation/configuration/calibration
mismatch or incomplete raw evidence does.

Stage identity is `source_hash(stage) + config_hash(stage)`. The simulation
source closure contains the recursively consumed Module A/B/C scientific code,
including `metrics/action_gaps.py` and `metrics/ranking_diagnostics.py`.
`metrics/monte_carlo.py` is aggregation-only; provenance/manifest writers are
infrastructure. `EXPERIMENT_DISPLAY_NAME` and figure/table IDs are reporting
metadata. Full Module A seed count and Module B replication count are scientific
design, while aggregation bootstrap replication count is downstream-only. The
legacy monolithic `config_hash` and complete source-tree hash remain
informational compatibility metadata.

For an accepted historical run whose hash definition predates this closure:

```powershell
python main.py migrate-provenance --run-dir outputs/runs/<run_id>
```

The migration reconstructs the corrected simulation hash from the recorded Git
commit and stops for human review if it differs from the corrected current hash.

## 9. Known Limitations
The experiment is limited to controlled recoverability diagnostics and does not support claims about real-world causal identification or policy validity.

# Experiment 4: Recoverability Boundary Diagnostic

## 1. Experiment Objective
This experiment studies the recoverability boundary of route alignment and audit reliability under controlled simulation settings. It evaluates whether route-label retention, source-signature noise, and finite evidence produce recoverable diagnostics without claiming causal identification.

## 2. Scientific Boundary
Experiment 4 is a recoverability boundary diagnostic. It does not identify a real-world causal attribution rule, prove proxy impossibility, or treat calibration improvement as route validity.

## 3. Data and Split
The design uses controlled simulation settings for module A, module B, and module C, with frozen route-label rates, source-signature noise levels, audit rates, and calibration-fold structure. The v2 schema is maintained for the formal outputs.

## 4. Estimand / Metrics
The primary estimands are action-gap defect, audit bias and RMSE under selective evidence, and calibration-family discrepancy diagnostics. The outputs are reported as recoverability diagnostics rather than policy value estimates.

## 5. Implementation Contract
The pipeline validates source-bound and full-label zero defect, action-pair invariants, positivity, temporal leakage constraints, affine recovery, and the Exp1-Exp4 boundary. The run and figure outputs are generated from frozen derived data and validated by the self-check mechanism.

## 6. Output Artifacts
Outputs are separated into calibration, module A, module B, and module C results, with figure bundles and tables written from the frozen derived outputs.

## 7. Validation and Self-check
The self-check validates scientific invariants and output consistency. Promotion remains a separate manual action that accepts only a completed full v2 run that passes the relevant gates.

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

## 9. Known Limitations
The experiment is limited to controlled recoverability diagnostics and does not support claims about real-world causal identification or policy validity.


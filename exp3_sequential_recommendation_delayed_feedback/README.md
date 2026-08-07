# Experiment 3: Logged-Supported Ranking Recovery

## 1. Experiment Objective
This experiment evaluates logged-supported ranking recovery using the frozen KuaiRand design, with score recovery, reference-pair gap recovery, and ranking recovery as the scientific chain.

## 2. Scientific Boundary
The experiment is a logged-support diagnostic. It does not estimate structural causal regret, causal action gaps, off-policy value, online policy value, deployment performance, or optimal recommendations.

## 3. Data and Split
The frozen design uses the fixed history and evaluation logs, a deterministic two-fold user split, support thresholds, time bins, and the constructed six-hour post-exposure target. The three route families are the arrival carrier, historical mean, and ridge proxy.

## 4. Estimand / Metrics
The primary estimands are pooled supported-cell Spearman, MAE, maximum reference-pair gap error, sign agreement, and paired ranking contrast. The route contrast is reported as the Ridge-over-Historical paired value gain.

## 5. Implementation Contract
The pipeline reconstructs the design contract, applies the route scores, audits target components, conducts support preflight checks, generates the primary metrics, and writes the self-check manifest. The ridge selection is part of the frozen logic and is validated independently.

## 6. Output Artifacts
Canonical outputs include the metric registry, primary route results, paired ranking contrast, support coverage, gap error distribution, target audit, ridge history cross-validation summary, and diagnostics tables.

## 7. Validation and Self-check
The independent self-check validates the frozen design, route support, ridge selection, target audit, and figure-data contract. Fast runs are engineering gates only and are not paper results.

## 8. Running Commands
```bash
python -m compileall .
pytest -q
python main.py fast --synthetic-fixture --n-jobs 4
python main.py self-check --mode fast --output-dir outputs/<fixture_run_id>
python main.py fast --n-jobs 4
python main.py self-check --mode fast --run-id <real_fast_run_id>
```

```bash
python main.py full --n-jobs <N>
python main.py self-check --mode full --run-id <new_full_run_id>
python promote.py --run-id <new_full_run_id>
```

## 9. Known Limitations
The experiment remains limited to logged-supported recovery and does not claim deployment or causal identification beyond the frozen contract.

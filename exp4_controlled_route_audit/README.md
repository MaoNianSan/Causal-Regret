# Experiment 4: Route Alignment and Evidence-Qualified Audit

Exp4 v2 is a controlled simulation and audit simulation. It does not identify a real-world causal attribution rule, prove proxy impossibility, or treat calibration improvement as route validity.

## Exp1-Exp4 Boundary

Exp1 owns learner consequences, regret transfer, and delay-mechanism comparisons. Exp4 owns three different quantities:

1. **Module A: Controlled Route-Alignment Boundary** varies route-label retention and source-signature noise, with population action-gap defect as the primary estimand.
2. **Module B: Evidence-Qualified Audit Reliability** holds the route fixed and estimates audit bias, RMSE, and effective support under finite/selective evidence.
3. **Module C: Calibration-Family Controls** evaluates out-of-fold affine discrepancy reduction without constructing a policy or coherent corrected loss map.

The three modules are not combined into a composite score.

## Frozen v2 Design

- Module A: `T=5000`, `W=250`, 100 formal shared seeds.
- Module B/C: `T=2000`, `W=100`, 1000 formal replications.
- Route-label rates: `0`, `0.3`, `0.7`, `1`.
- Source-signature noise SDs: `0`, `0.10`, `0.25`, `1.00`.
- Audit rates: `0.10`, `0.30`, `0.50`, `1.00`.
- Calibration uses 20 independent seed IDs, a median-distance kernel bandwidth, an empirical smoothed delay PMF, and five contiguous temporal folds.
- V2 schema: `exp4_controlled_route_audit_v2`.

See [MIGRATION_V1_TO_V2.md](MIGRATION_V1_TO_V2.md) for the field and machine-ID migration.

## Install

```powershell
python -m pip install -r requirements.txt
```

## Run Tiers

```powershell
python main.py fast --n-jobs 4
python main.py middle --n-jobs 8
python main.py full --n-jobs 8
```

| Tier | Module A seeds | Module B/C replications | Bootstrap | Promotion |
|---|---:|---:|---:|---|
| fast | 3 | 10 | 0 | refused |
| middle | 20 | 100 | 500 | refused |
| full | 100 | 1000 | 2000 | separate approval only |

All tiers use the formal scientific horizons. A completed full run remains `paper_result=false`.

## Stage Commands

```powershell
python main.py validate --run-dir outputs/runs/<run_id>
python main.py aggregate --run-dir outputs/runs/<run_id>
python main.py plot --run-dir outputs/runs/<run_id>
python main.py tables --run-dir outputs/runs/<run_id>
python main.py report --run-dir outputs/runs/<run_id>
```

Resume a partially completed tier with explicit stage manifests:

```powershell
python main.py middle --resume-run-dir outputs/runs/<middle_run_id> --n-jobs 8
```

## Outputs

Module outputs are separated under:

```text
derived/calibration/
derived/module_a/
derived/module_b/
derived/module_c/
```

The main figure is:

```text
figures/pdf/fig_exp4_route_alignment_and_audit_reliability.pdf
```

The main table is:

```text
tables/tbl_exp4_calibration_controls.tex
```

Every figure bundle contains PDF, PNG, source CSV, metadata JSON, source hashes, config hash, calibration hash, code commit, schema, tier, and paper status. Figure and table code reads frozen derived outputs and does not import simulation, route, audit, or calibration engines.

## Scientific Gates

The run validates source-bound and full-label zero defect, all 45 action pairs, positive attribution mass, no future candidates, independent route/audit streams, label-blind ambiguity, the Definition 4.3 defect formula, shared selective masks, IPW positivity, no temporal leakage, affine parameter recovery, blocked correspondence destruction, reconstructable figures, Monte Carlo precision, and the Exp1-Exp4 boundary.

Calibration never falls back silently. Non-estimable folds retain explicit status and missing numeric outputs.

## Promotion

Promotion is a separate manual action and accepts only a passed full v2 run whose Monte Carlo precision gate is `PASS`:

```powershell
python promote_results.py --run-dir outputs/runs/<full_run_id> --approve-claims
```

Fast, middle, v1, and legacy outputs are refused.

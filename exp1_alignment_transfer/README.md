# Experiment 1: Controlled Alignment and Regret Transfer

## 1. Experiment Objective
This experiment tests whether action-gap alignment, rather than delay magnitude alone, governs whether route-level optimization can control structural regret.

## 2. Scientific Boundary
The implementation separates two distinct objects:
- route-map diagnostic: simulator-only full-map analysis of route validity and regret transfer;
- learner consequence: the same contextual Delayed EXP3 learner under arrival-clock and source-round scalar-feedback binding.

## 3. Data and Split
The frozen design uses the fixed simulation settings in the package configuration, including the listed delay mechanisms and evaluation/calibration seed grids. Formal runs require the parquet engine and respect the frozen calibration artifacts.

## 4. Estimand / Metrics
The core estimand is the bounded structural loss associated with the route-level alignment diagnostic, with calibration and bootstrap summaries reported from the frozen scientific outputs.

## 5. Implementation Contract
The implementation is organized around the frozen configuration, calibration workflow, route-map diagnostics, delayed learner execution, derived outputs, self-check, targeted validation, plotting, and promotion. The scientific source tree is validated by calibration lineage and self-check gates.

## 6. Output Artifacts
Main outputs are written under the run-tier output tree and include raw data, seed metrics, derived tables, figures, checks, metadata, and manuscript artifacts. The paper candidate is produced from frozen derived data only.

## 7. Validation and Self-check
Use the formal self-check and targeted validation commands before any promotion step. The package hard-fails when required scientific invariants or calibration checks do not pass.

## 8. Running Commands
```bash
python -m pip install -r requirements.txt
python calibrate.py
python main.py fast
python self_check.py --run fast
python targeted.py --run fast
python plot_main.py --run fast
python plot_appendix.py --run fast
```

```bash
python main.py full
python self_check.py --run full
python targeted.py --run full
python plot_main.py --run full
python plot_appendix.py --run full
python promote.py --run full
```

## 9. Known Limitations
Presentation-only rebuilds do not rerun the scientific experiment. Formal full runs remain separate from presentation-only regeneration and require the existing frozen artifacts.

## 10. Selective Rebuild Without Scientific Rerun
`reconcile.py` is the only supported reuse interface for an existing run. It
requires explicit run lineage, stage provenance, compatible scientific and
calibration hashes, complete raw/seed artifacts, and a prior scientific PASS.
It never reruns the primary scientific full or changes `raw/`, path manifests,
or seed-level scientific artifacts. A validation rebuild may rerun only the
separately classified targeted-validation grids.

```bash
python reconcile.py --source-run outputs/full --audit
python reconcile.py --source-run outputs/full --rebuild validation
python reconcile.py --source-run outputs/full --rebuild aggregation
python reconcile.py --source-run outputs/full --rebuild reporting
python reconcile.py --source-run outputs/full --rebuild downstream
```

`validation` reruns checks and targeted validation; `aggregation` rebuilds derived
outputs and validation; `reporting` rebuilds figures and tables; `downstream`
rebuilds aggregation, validation, and reporting. Each rebuild records
`metadata/exp1_provenance_reconciliation.json`. A scientific-generation,
scientific-generation source/config, or calibration mismatch refuses reuse and
requires a separately approved full scientific run. Bootstrap/CI changes are
aggregation rebuilds, theorem-sweep changes are validation rebuilds, and
`DISPLAY_NAMES` changes are reporting rebuilds. The historical `config_hash`
remains as `legacy_complete_config_hash` metadata and is not a reuse gate.

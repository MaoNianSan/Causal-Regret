# Exp3 code audit report — rerun-ready package

## Audit outcome

The core Exp3 specification and the implemented chronology are internally consistent in this package:

- the action vocabulary is built from history-standard only;
- the 6h target is constructed from within-split future standard-log engagement;
- carrier assignment uses the most recent same-user exposure at or before arrival;
- partial labels update source actions when labelled and arrival carriers otherwise;
- ridge proxies are fit on history and score the main split using completed history plus earlier main bins only;
- the history-mean static control is retained;
- user-cluster bootstrap, static-control paired effects, label-mask-bank uncertainty, and audit summaries are present;
- active figure interfaces are the main recoverability figure and horizon eligibility figure only.

## Repaired execution and output defects

- Fixed UTF-8 failure when a recovered zip is extracted under a path containing surrogate characters.
- Replaced direct CSV and JSON writes with atomic writes.
- Added a stale-output guard and explicit `--clean-output` control.
- Ensured a missing-input full invocation blocks before touching a previous `outputs/full/` tree.
- Preserved promotion status in `self_check_report.csv`.
- Rebuilt release validation logic so release manifests and checksum indices cannot self-reference, checksum sidecars are validated, and both archives must contain active figure bundles and release documentation.
- Corrected malformed README output-section fencing and added a detailed rerun/output guide.

## Executed checks in the repair environment

```text
python code_check.py                    PASS
python tests/test_temporal_contracts.py PASS
python reproduce_fast.py --n-jobs 2 --clean-output  PASS (synthetic fixture)
python self_check.py --mode fast       PASS
python reproduce_full.py --n-jobs 2 --clean-output  BLOCKED as intended because raw KuaiRand files were not included
```

## Limit of this audit

The package contains no KuaiRand raw input files, so a real-data fast or full execution was not performed in this repair environment. The required real-data rerun commands are in `RUN_THIS_FIRST.txt`, `README.md`, and `docs/rerun_output_guide.md`.

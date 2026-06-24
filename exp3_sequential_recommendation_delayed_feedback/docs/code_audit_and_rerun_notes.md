# Code audit and rerun notes

## Scope of this repair

The experiment definition, target, action vocabulary, proxy formulas, carrier rule, partial-label update rule, bootstrap estimand, and full-run settings are unchanged. The repair addresses execution reliability, output provenance, and release-integrity checks.

## Fixed execution issues

1. **UTF-8-safe metadata and CSV output.** A storage-recovery or cross-platform zip extraction can leave surrogate characters in a parent directory name. Previously, an absolute input path written to `input_data_manifest.csv` could make fast mode fail with `UnicodeEncodeError`. Metadata paths are now logical relative paths, and CSV/JSON writes escape only unencodable code points.
2. **Atomic CSV and JSON writes.** Output tables, manifests, and figure-data CSVs are first written to a temporary file in the destination directory and then atomically replaced. A failed process is less likely to leave a half-written active artifact.
3. **Stale-output guard.** A new run refuses to use an existing active output tree unless `--clean-output` is passed. This prevents a fresh run from mixing with stale summaries, tables, figures, or checks.
4. **Safe full-input gate.** If the three real KuaiRand inputs are absent, `reproduce_full.py` blocks before clearing or changing `outputs/full/`.
5. **Promotion-report consistency.** `self_check_report.csv` records `paper_result` and `promotion_status`. A normal self-check after promotion now reports `already_promoted` instead of appearing to reverse promotion.
6. **Release integrity logic.** Release manifests and checksum indices exclude their own files, checksum sidecars are validated, active figure bundles are required in both archives, and final release reports are included in archive membership checks.
7. **Documentation repair.** The README output section and code fences were normalized, and this rerun guide documents each expected output family.

## Required commands

```bash
python code_check.py
python tests/test_temporal_contracts.py
python reproduce_fast.py --n-jobs 12 --clean-output
python self_check.py --mode fast
```

For the actual experiment after confirming real fast outputs:

```bash
python reproduce_full.py --n-jobs 24 --clean-output
python self_check.py --mode full
python self_check.py --mode full --promote-paper-result
python self_check.py --mode full
```

## Expected status fields

### Real-data fast

```text
input_data_status = real_kuairand_1k
run_mode = fast
status = complete_pending_external_checks
paper_result = false
```

### Promoted full

```text
input_data_status = real_kuairand_1k
run_mode = full
status = complete
paper_result = true
```

## Important non-fixes

This repair does not change the scientific interpretation of Exp3. In particular, it does not modify any of:

- the constructed 6h target;
- the pseudo-arrival mechanism;
- the history/main chronological split;
- the carrier assignment;
- the partial-label mask design;
- the proxy model or ridge hyperparameters;
- the daily action aggregation;
- the 1,000 user-bootstrap or 30-mask full protocol.

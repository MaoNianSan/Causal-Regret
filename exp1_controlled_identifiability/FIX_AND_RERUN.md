# EXP1 code audit, repairs, and rerun protocol

## Repairs included in this package

1. Corrected the archived source contract so that `source_labelled` is a main
   conditional recovery method, not an oracle reference.
2. Removed stale scenario-id dependencies from the output rebuild path.
3. Replaced the misleading parallel full-trace behavior. Standard runs now
   write summary-level results and a compact selected-trajectory audit only.
   Detailed traces require an explicit single-worker audit run.
4. Added current-schema raw-result rebuilding.
5. Standardised seed uncertainty to `2000` percentile-bootstrap resamples.
6. Added complete summary CSV, table CSV, LaTeX-table, figure-data, and
   figure-metadata contracts.
7. Replaced cross-regime bar comparisons with regime-consistent point-range
   figures.
8. Added self-check gates for output completeness, bootstrap settings, figure
   schema, EM likelihood, proxy feature alignment, feedback accounting, and
   trace logging mode.
9. Added `finalize_paper_outputs.py`, which is the only mechanism that can
   mark a completed full run as `paper_result=true`.

## Required order

```powershell
python code_check.py
python reproduce_fast.py
python self_check.py --mode fast
python reproduce_full.py
python self_check.py --mode full
python finalize_paper_outputs.py --mode full
```

## Expected final full-run checks

The full manifest must report:

```text
backend_status=completed
completed_runs=7920
expected_runs=7920
mode=full; run_mode=full
raw_log_mode=summary_only
paper_result=false
n_bootstrap=2000
```

After `finalize_paper_outputs.py --mode full`, the full bundle may report
`paper_result=true` only if the full self-check has passed.

## What not to infer

- Fast results are not paper results.
- The standard parallel full run does not retain all event-level trace rows.
- Source-labelled methods are conditional on source-label availability.
- Gaussian-integrated EM is not claimed to dominate all delay mechanisms.
- Equal realised mean delay does not imply equal censoring, arrival geometry,
  or learning difficulty.

# Exp4 fast review - 2026-07-26

## Scope

This review is limited to the fast tier. No full run or paper-result promotion was executed.

## Corrected issues

1. `fig_app_exp4_calibration_distributions`
   - The right panel was not missing data. All three negative-recoverability rates were exactly zero in the fast output.
   - Zero-height bars were invisible on the axis baseline.
   - Exact zeros are now shown with a diamond marker and a numeric `0.00` annotation.
   - The y-axis uses an informative dynamic upper bound when all rates are zero.

2. `fig_app_exp4_four_route_comparison`
   - The Source-labelled ranking-reversal rate was not missing; it was exactly zero.
   - The same invisibility affected Source-labelled action-gap defect and structural regret per round.
   - Exact-zero values in all four-route bar panels are now shown with a diamond marker and a numeric `0` annotation.
   - Finite confidence intervals will also be drawn when the full tier produces bootstrap intervals.

## Additional engineering corrections

1. Run manifests previously stored machine-specific absolute paths. They now store paths relative to the run directory.
2. Self-check path resolution remains compatible with relocated legacy runs where the stored absolute path no longer exists.
3. The duplicated `[5/6]` progress label was removed; the six-stage console sequence is now unambiguous.
4. Static checks now verify zero-value rendering support and portable run-manifest paths.

## Fast validation result

The final fast validation completed all six stages with:

- Engineering status: `PASS`
- Scientific status: `PASS`
- Paper promotion: `NOT_RUN`
- `paper_result`: `false`

All six PNG/PDF figure bundles were generated. PDF preflight reported no warnings, and rendered inspection found no clipping, overlap, blank panels, or broken glyphs.

Expected fast-tier behavior:

- Bootstrap confidence-interval columns remain `NA` in fast mode.
- These columns are populated only in the full tier and are not treated as missing-output defects.

## Environment qualification

The review environment did not provide `pyarrow`. A validation-only storage shim was therefore used to exercise the complete simulation, aggregation, plotting, table, engineering-check, and scientific-check control flow. The shim was not added to the project and no shim-generated `.parquet` file is included in the corrected package.

Before starting full, run the formal fast command in the target environment with the declared dependencies:

```bash
python -m pip install -r requirements.txt
python clean.py
python main.py fast
```

Proceed to `python main.py full` only if that formal fast run again reports both engineering and scientific `PASS`.

## Scientific review item, not a code gate

In the five-replication fast result, the shuffled negative control had positive estimated recoverability. The programming memo explicitly states that shuffled-control recoverability must not be forced to zero and must not be used as an engineering gate. Do not interpret the fast result as evidence of stable recoverability or non-recoverability; reassess its distribution after the full Monte Carlo run.

# EXP1 rerun-readiness report

## Completed repairs

- Preserved the contextual information comparator and shared-path delay design.
- Preserved source-time proxy feature alignment and Gaussian-integrated EM.
- Removed stale output-rebuild dependencies on retired scenario IDs and raw
  columns.
- Replaced misleading parallel detailed-trace placeholders with an explicit
  summary-only production contract and single-worker trace-audit guard.
- Added seed-level summaries, bootstrap outputs, table outputs, figure-data
  CSVs, figure metadata, and paper-result gating.
- Standardised uncertainty to `2000` seed-bootstrap resamples.
- Registered main and appendix figures with reproducible data/metadata bundles.
- Removed stale executed notebooks and historical output references from the
  clean rerun package.

## Validation completed

- Python compilation across the package.
- `code_check.py` with the complete `264`-combination smoke design.
- Raw-output rebuild from the current schema.
- `self_check.py` on the generated smoke bundle.
- Single-worker trace-audit smoke generation with non-empty schedule, arrival,
  and step files.

## Not included

No completed fast/full numerical result is included. A new run must generate
all paper-facing numerical results from the supplied source.

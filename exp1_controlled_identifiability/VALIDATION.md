# Validation record for the rerun-ready source package

## Completed code validation

- All Python modules compile successfully.
- `python code_check.py` passed after the current output-contract repairs.
- The code check ran the complete `264`-combination smoke design and passed the
  internal self-check.
- The rebuild path was tested from current-schema raw results using
  `rebuild_outputs_from_raw.py` and passed self-check.
- A one-worker trace-audit smoke run produced non-empty schedule, arrival, and
  step trace files. This verifies that detailed traces are written only when
  their requested logging mode is feasible.
- A targeted `T=5000` state-structural Gaussian-integrated EM run completed
  with one effective feedback unit per observed arrival and the expected
  integrated-delay-likelihood identifier.

## Verified modelling and fairness contracts

- All learners receive the same public decision-time context.
- Regret uses the context-information comparator rather than a full-state
  comparator unavailable to non-reference learners.
- Main matched-delay settings share policy-independent state, context, and
  delay paths within each seed.
- Matched delays are calibrated using finite-horizon realised observed delay.
- Source-labelled and proxy learners use source-time saved features for
  labelled feedback updates.
- Arrival-time, source-labelled, EM, and proxy routes update per arrived source
  outcome rather than by batch average.
- The default structural EM uses observable-state Gaussian integration; the
  stationary-geometric route is a diagnostic ablation.
- Seed uncertainty uses a `2000`-resample percentile bootstrap contract.

## Deliberately absent from this package

The package contains no formal fast or full numerical results. The `outputs/`
directory is intentionally clean so that a rerun cannot mix stale results with
new results. Run the commands in `README.md` before interpreting any numerical
output as a result.

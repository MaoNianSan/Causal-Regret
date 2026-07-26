# Implementation status

## Implemented

- Normalized directory, experiment, module, route, parameter, estimand, file, and display naming.
- Separate deterministic `structural_loss_map` and noisy `realized_potential_feedback`.
- Extended observation clock to `decision_horizon + maximum_candidate_delay`.
- Named `SeedSequence` random streams and path hashes.
- Full-map Source-bound, Arrival-time, History-surrogate, and Proxy-label routes.
- Module A 4-by-3 primary route-boundary grid and pairwise diagnostics.
- Appendix scalar-feedback UCB consequence with full-label action-trace invariant.
- Independent route-label and audit-evidence streams.
- Label-blind observable attribution-entropy ambiguity score.
- MCAR, ambiguity-biased unweighted, and ambiguity-biased IPW audits.
- Five-fold contiguous temporal pair-specific affine cross-fitting.
- Raw and conditional calibrated population targets.
- Affine positive, shuffled negative, and appendix nonlinear controls.
- Module B replication outputs, Monte Carlo summaries, support diagnostics, and main table.
- Paper-facing main figure with panels (a), (b1), (b2), and (c), plus five appendix figures.
- Engineering, scientific, reconstruction, static code, and independent promotion checks.
- Full execution remains `paper_result=false`; promotion is explicit.
- Independent safe cleaner and legacy migration record.

## Validation completed in the build environment

- Python compilation: PASS.
- Static code-contract check: PASS.
- Source-bound population action-gap defect: exactly 0 in the smoke trajectory.
- Proxy-label defect at route-label rate 1: exactly 0 for all primary proxy-noise values.
- Full-label Proxy-label learner action trace equals Source-bound learner action trace.
- One Module A seed completed: 15 route records, 675 pair records, 7 learner records.
- One Module B smoke replication completed: 3,600 audit-unit records, 40 raw estimates, 40 calibrated estimates, 9,675 calibration-parameter records, and 3 calibration controls.

## End-to-end orchestration validation

The complete fast orchestration, figure generation, table generation, engineering checks, scientific checks, raw-target reconstruction, and conditional calibrated-target reconstruction were exercised with an in-process development storage shim. Engineering and scientific status both passed. The resulting development artifacts were removed and are not distributed as formal outputs.

The canonical Parquet-backed command was not run in the build environment because the environment does not provide a Parquet engine and cannot install `pyarrow` from its restricted package index. Parquet is intentionally retained as a required dependency rather than replaced by a silent non-Parquet fallback.

After installing `requirements.txt`, run:

```text
python main.py fast
```

Only after the fast run passes should the formal full run be launched.

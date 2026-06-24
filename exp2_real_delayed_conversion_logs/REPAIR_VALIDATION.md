# Experiment 2 rerun-readiness validation

## Scope

This validation covers the clean-rerun code path for the source-time decision-cell version of Experiment 2. The package was checked after correcting four rerun blockers:

1. a clean run no longer requires a historical display-only hash snapshot;
2. the delay composition is counted over eligible source-event rows, not unique conversion IDs;
3. UID sentinels `-1` and `-1.0` are treated as missing and audited before clustering;
4. the synthetic fixture configuration now matches the current route and scientific-gate contract.

A fifth runtime correction removes nested UID bootstrap from the appendix-only candidate-window diagnostic. The main route-sensitivity summary remains the only inferential object and retains its configured UID bootstrap.

## Validation executed

The following synthetic integration test completed successfully on 2026-06-24:

```text
python tests/run_synthetic_integration.py
```

It ran the complete fast pipeline twice against a synthetic fixture:

```text
precheck -> timeline -> route_assignment -> statistics -> figures -> tables -> self_check
```

The two passes used `--n-jobs=1` and `--n-jobs=4`. The UID-bootstrap output hashes were identical. The final synthetic run completed with 69 semantic checks and zero failures, followed by a passing static code check.

The recorded synthetic step times for the `--n-jobs=4` pass were approximately:

| Step | Elapsed time |
|---|---:|
| precheck | 3.5 s |
| timeline | 4.4 s |
| route assignment | 6.4 s |
| statistics | 15.7 s |
| figures | 6.6 s |
| tables | 4.4 s |
| self-check | 3.2 s |

The synthetic timing is only a control-path check and is not a forecast for the real Criteo run.

## Code and contract checks

The final synthetic pass confirmed all of the following:

- clean fast execution succeeds without a historical replot hash snapshot;
- source-event delay profile fields are `n_eligible_source_events` and `source_event_share_percent`;
- missing UID values and `-1` / `-1.0` UID sentinels are filtered and audited;
- conversion IDs with non-unique UIDs remain hard failures after integrity filtering;
- candidate-window diagnostics use a common cohort and window-specific UID compatibility audit;
- candidate-window diagnostics are point estimates only, with `window_bootstrap_replicates=0` and an explicit uncertainty-status field;
- source-time decision-cell action construction is retained;
- the main route sensitivity still uses UID-cluster bootstrap;
- route-degeneracy scientific gates, figure/table contracts, and paper-result gates remain active;
- `--n-jobs=1` and `--n-jobs=4` generate identical UID-bootstrap replicate files on the fixture;
- source code compiles and static code checks pass.

## Real-data rerun boundary

No real Criteo fast or full run was executed during this validation. The package intentionally contains no protected raw input and no synthetic result files in `outputs/`.

Place the real data at:

```text
inputs/pcb_dataset_final.tsv
```

Then execute the real fast run first. Do not reuse any old `outputs/fast` or `outputs/full` directory; `main.py` removes the selected mode directory before it starts.

## Expected output progression

The real runner prints elapsed seconds for each completed step. For the candidate-window appendix diagnostic it also prints four window-specific point-estimate steps. These are expected to be slower than the main UID bootstrap for some inputs, but they do not launch nested bootstrap jobs.

The full run is eligible for paper-result finalization only after the final semantic check succeeds. Any failed integrity, route-degeneracy, or figure/table contract leaves `paper_result=false`.

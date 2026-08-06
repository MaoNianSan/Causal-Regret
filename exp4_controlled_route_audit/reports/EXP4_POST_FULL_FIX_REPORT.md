# Exp4 v2 Post-Full-Fix Report

Status date: 2026-08-06
Scope: `exp4_controlled_route_audit` only
Existing full run: `full_20260806T021401Z_5627f17b`

## 1. Root causes

### 1.1 Empty main calibration table

- The Module C control summary was assigned a blanket `analysis_tier = "mixed"`
  by `exp4/execution/aggregation_stage.py::_module_c_frames` via
  `attach_metadata(..., tier="mixed", ...)`, which overwrote every row's tier.
- The main-table generator selected rows with `analysis_tier == "primary"`, so
  the selection was empty and the CSV/LaTeX contained only headers.
- `main_table_complete` only checked file existence, so engineering checks and
  promotion passed despite the empty table.

### 1.2 Monte Carlo precision gate recorded as NOT_APPLICABLE_NON_FULL

- The full run's `MONTE_CARLO_PRECISION` scientific check accepted
  `NOT_APPLICABLE_NON_FULL` regardless of `run_tier`; the primary contrast in
  the existing full run carried `NOT_APPLICABLE_NON_FULL`.
- The paired-contrast aggregation located the primary row with
  `primary_rows.index[0]`, which is the first index label (row 0), not the
  flagged primary row — the gate was applied to the wrong contrast.
- Promotion checked only that the `MONTE_CARLO_PRECISION` scientific row was
  `PASS`, which it was, so the run was promoted despite an ungated primary
  contrast.

### 1.3 Provenance ambiguity

- The recorded `code_commit` (`889bc771…`) predates the `exp4/` v2 package
  (first committed in `339a5d7…`); the stored `source_code_hash`
  (`52e2ca0b…`) cannot be reproduced from any current file set and differs from
  the current pre-fix hash (`0cce5bf3…`). The raw simulation source could not
  be shown unchanged, so simulation provenance is unverified.

### 1.4 Stale status report

- `reports/EXP4_V2_IMPLEMENTATION_STATUS.md` hard-coded `FULL_RUN_EXECUTED=NO`
  while a full run exists.

## 2. Modifications

| Kind | File |
| --- | --- |
| Modified | `exp4/configuration/schema.py` (exact `MAIN_CALIBRATION_CONTROL_IDS`) |
| Modified | `exp4/execution/aggregation_stage.py` (per-control tier preserved) |
| Modified | `exp4/outputs/writers.py` (shared source-hash function + algorithm version) |
| Modified | `exp4/pipeline.py` (stage provenance record on fresh runs) |
| Modified | `exp4/reporting/aggregate_module_a.py` (primary-row gate fix; REPORTED_NOT_GATED) |
| Modified | `exp4/reporting/aggregate_module_c.py` (authoritative CONTROL_REGISTRY tiers) |
| Modified | `exp4/reporting/tables.py` (exact control-ID selection + table manifest) |
| Modified | `exp4/validation/invariants.py` (tier-aware MONTE_CARLO_PRECISION) |
| Modified | `exp4/validation/runner.py` (semantic main-table + precision engineering checks) |
| Modified | `main.py` (status + provenance subcommands; stage provenance on downstream) |
| Modified | `promote_results.py` (re-derived gates; provenance gates; `--dry-run`) |
| Modified | `reports/EXP4_V2_IMPLEMENTATION_STATUS.md` (auto-generated) |
| Added | `exp4/reporting/implementation_status.py` |
| Added | `exp4/validation/table_checks.py` |
| Added | `exp4/validation/precision_checks.py` |
| Added | `exp4/validation/run_provenance.py` |
| Added | `reports/EXP4_FULL_PROVENANCE_AUDIT.md` / `.json` |
| Added | `tests/unit/test_table_checks.py`, `test_precision_checks.py`, `test_run_provenance.py`, `test_implementation_status.py` |
| Added | `tests/regression/test_post_full_fix_regression.py` |
| Modified | `outputs/runs/full_20260806T021401Z_5627f17b/checks/exp4_promotion_check.json` (dry-run result, now FAIL) |

- Deleted files: none.
- Schema change: no result-schema change; `exp4_controlled_route_audit_v2`
  unchanged. New check artifacts (`exp4_table_checks.json`,
  `exp4_precision_checks.json`, `exp4_stage_provenance.json`,
  `exp4_provenance_reconciliation.json`, `exp4_main_table_manifest.json`) and a
  `source_hash_algorithm_version` field in `run_config.json` were added.
- Scientific estimand change: none. Module A/B/C definitions, frozen
  parameters, and the affine/blocked/nonlinear control families are unchanged.
  `nonlinear_monotone` moved from the (broken) primary selection into the
  appendix tier, matching the frozen `CONTROL_REGISTRY`.

## 3. Verification

- Compile: `python -m compileall -q .` PASS.
- Pytest: 45 passed (was 13 before this round).
- `git diff --check`: PASS.
- Lint/type: `ruff` and `mypy` are not installed locally; reported honestly, no
  dependency changes were made.
- Fast regression `python main.py fast --n-jobs 4`
  (`fast_20260806T071500Z_2efad11d`): engineering PASS, scientific PASS.
  - Main table has exactly two rows: Affine-linked control, Temporally blocked
    correspondence-destroyed control; nonlinear monotone excluded.
  - `MONTE_CARLO_PRECISION` PASS with `run_tier=fast; primary_contrasts=1;
    ids=[q_0.7_to_1__sigma_0.25]; gates=[NOT_APPLICABLE_NON_FULL]`.
  - Non-primary contrasts carry `REPORTED_NOT_GATED`.
  - `EXP1_EXP4_BOUNDARY` PASS (`banned_terms_present=[]`).
  - `source_hash_algorithm_version=exp4-source-code-v1` present; stage
    provenance record written.
- Main-table semantic check: PASS on fast (12/12 semantic sub-checks).
- Precision checks: PASS on fast; the promotion-level precision gates were
  added and exercised.
- Provenance: audit generated
  (`reports/EXP4_FULL_PROVENANCE_AUDIT.md`/`.json` and
  `logs/exp4_provenance_audit.json`).
- Promotion dry-run on the existing full run: **FAIL** (see below).

## 4. Full-run handling

```text
FULL_SIMULATION_RERUN_REQUIRED=YES
FULL_SIMULATION_REUSED=NO
DOWNSTREAM_ARTIFACTS_REBUILT=NO
FULL_RUN_ID=full_20260806T021401Z_5627f17b
```

The stored `source_code_hash` cannot be matched to the current source
(`source_hash_match=false`), so per the reuse rule the raw simulation is not
reused and the existing full run is not promoted. No raw simulation outputs
were modified. The erroneous `paper_result=true` set by the pre-fix promotion
was reverted to `false`/`NOT_RUN` (the four protected provenance fields
`code_commit`, `source_code_hash`, `config_hash`, `calibration_hash` were left
untouched).

Promotion dry-run on the existing full run refused with:
`main_table_complete=false`, `main_table_has_required_rows=false`,
`main_table_latex_nonempty=false`, `main_table_values_finite=false`,
`monte_carlo_precision_pass=false`,
`no_nonfull_precision_status_in_full_run=false`,
`primary_monte_carlo_precision_pass=false`,
`simulation_provenance_verified=false`,
`source_hash_algorithm_version_present=false`.

## 5. Exp1/Exp4 boundary

```text
EXP1_EXP4_BOUNDARY=PASS
LEARNER_RESULT_ADDED_TO_EXP4=NO
STRUCTURAL_REGRET_PRIMARY_IN_EXP4=NO
CALIBRATION_POLICY_CREATED=NO
```

No learner/UCB, structural regret, route regret, transfer bound, or calibration
policy artifacts were introduced. `MIDDLE_RERUN_REQUIRED=NO` — no simulation,
route, audit-estimator, or calibration numerical logic was modified.

## 6. Git operations

```text
GIT_COMMIT_EXECUTED=NO
GIT_PUSH_EXECUTED=NO
```

Per instructions, no commit or push was performed. The user will commit and
push the changes themselves.

## 7. Next command

```powershell
python main.py full --n-jobs 8
```

After the new full run completes, run `python main.py status`, then the
promotion dry-run, then (only if it passes) the human promotion:
`python promote_results.py --run-dir <new_full_run_dir> --approve-claims --dry-run`.

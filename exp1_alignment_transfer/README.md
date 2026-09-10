# Experiment 1: Controlled Alignment and Regret Transfer

## Overview

This experiment tests whether **action-gap alignment**, rather than delay
magnitude alone, governs whether route-level optimization can control
structural regret under delayed feedback. The implementation separates two
distinct objects:

- **route-map diagnostic**: simulator-only full-map analysis of route validity
  and regret transfer;
- **learner consequence**: the same contextual Delayed EXP3 learner under
  arrival-clock and source-round scalar-feedback binding.

This is a controlled-simulation experiment. The authoritative input/output
contract (units, mechanisms, config hashes, metrics, uncertainty semantics) is
in [`docs/EXPERIMENT_IO_CONTRACT.md`](../docs/EXPERIMENT_IO_CONTRACT.md).

## Input

- **Data availability**: `AVAILABLE_IN_REPO` — no external raw dataset.
- The frozen simulation settings live in `config.py`; the frozen calibration
  artifacts (delay, misbinding, structural, and context calibration JSON +
  manifest) live in `calibration/`.
- Formal runs require the parquet engine and respect the frozen calibration
  artifacts.

## Run

```bash
python -m pip install -r requirements.txt
python calibrate.py

# Fast tier (engineering gate; not a paper result)
python main.py fast
python self_check.py --run fast
python targeted.py --run fast
python plot_main.py --run fast
python plot_appendix.py --run fast

# Formal full run + promotion
python main.py full
python self_check.py --run full
python targeted.py --run full
python plot_main.py --run full
python plot_appendix.py --run full
python promote.py --run full

# Additive targeted-extension promotion (separate scope-specific authorization;
# never replaces the primary candidate)
python promote_targeted.py --dry-run
python promote_targeted.py
```

Selective rebuild of a downstream stage without a scientific rerun uses
`reconcile.py --source-run outputs/full --rebuild {validation,aggregation,
reporting,downstream}` (see `REPRODUCE.md` section D.1).

## Output

Main outputs are written under the run-tier output tree (`outputs/`) and
include raw data, seed metrics, derived tables, figures, checks, metadata,
and manuscript artifacts. The paper candidate is produced from frozen derived
data only.

## Paper-facing artifacts

- Canonical result: `outputs/paper_candidate/` (schema current **v1.2**,
  `paper_result=true`).
- Source full run: `exp1_alignment_transfer:full:2026-08-17T06:28:21.157011+00:00`
  (code_commit `23199c48`).
- Publication bundle: `../publication/CR-EXP-OUTPUT-V1/exp1_alignment_transfer/`
  (main figure ID `fig_exp1_alignment_transfer`).

### Two promotion scopes

`promote.py` and `promote_targeted.py` answer different questions and are not
interchangeable.

| | primary promotion | targeted-extension promotion |
|---|---|---|
| entry point | `promote.py --run full --force` | `promote_targeted.py` |
| effect | deletes and rebuilds `outputs/paper_candidate/` from `outputs/full` | copies an explicit allowlist into the existing candidate |
| authorization | `paper_promotion_authorized: YES` memo | approved memo declaring `authorized_promotion_scope: targeted_extension` **and** the exact snapshot binding |
| analysis tier | `primary` | stays `targeted` |
| manifest | `outputs/paper_candidate/exp1_promotion_manifest.json` | `outputs/paper_candidate/metadata/exp1_targeted_promotion_manifest.json` |
| status | `status/paper_promotion_status.json` | `status/targeted_paper_promotion_status.json` |

The targeted gate binds the authorization to the accepted snapshot
(`authorized_source_run_id`, `authorized_scientific_generation_hash`,
`authorized_validation_hash`, `authorized_targeted_validation_report_sha256`,
`authorized_cancellation_invariants_sha256`). A memo approved for an earlier
primary snapshot therefore never authorizes a targeted extension: it is
reported as stale and the promotion is blocked. The scope-specific
authorization is `CHANGE_MEMO_EXP1_006_TARGETED_PROMOTION_DRAFT.md`, approved
2026-09-10, and the targeted promotion was executed the same day.

Before authorization the gate stops at
`TARGETED_PROMOTION_READY_EXCEPT_AUTHORIZATION` with a dry-run report; after
authorization it copies the allowlist, re-verifies that `outputs/full` and every
pre-existing primary candidate artifact are byte-identical, refreshes the
candidate's own artifact index for the promoted destinations only
(`metadata/artifact_manifest.json`; every other entry must stay exactly as
recorded), and writes the targeted manifest and status.

## Validation

The formal self-check and targeted validation must report `PASS` before any
promotion step. The package hard-fails when required scientific invariants or
calibration checks do not pass. `reconcile.py` is the only supported reuse
interface for an existing run and never reruns the primary scientific full or
changes `raw/` or seed-level scientific artifacts.

## Targeted diagnostics (route-map-only, non-promoted)

`targeted.py` additionally reports three diagnostics that never call the
learner, never write into `raw/` or `seed_metrics/`, stay `paper_result=false`,
and do not add a mechanism to `MECHANISM_ORDER`:

- **Horizon route quantities** reuse the frozen shared-prefix levels
  `T = {1000, 5000, 10000}` and the *same* generated bundle as the learner
  horizon check (no second path). The arrival-assigned route is the
  manuscript-facing curve; source-bound rows are kept for consistency only.
- **Cancellation sweep** is route-map-only and matched across an
  action-invariant shared level component and an action-dependent residual:
  `L_route[t, a] = L[t, a] + alpha_shared * c_t + u_t[a]` on the frozen
  eligible-round support. `static_shared` is `c_t = 1`; `state_varying_shared`
  is `c_t = 1 + S_t`, i.e. the same value is added to every action of a round,
  so `c_t` stays in `[0, 2]` by construction. Changing the shared component
  changes loss levels only: delta, rho, chi, complete conflict, the optimal
  masks and the all-action regret map must be unchanged up to the sweep
  tolerance, while the action-dependent residual is what moves them.
  Its hard C4 gate is checked in the native scale `delta_t = alpha_dep * mu_t`
  with tolerance `ratio_tol * mu_t + 32 * eps * max(1, |L_row|, |L_route_row|)`;
  the normalized ratio `delta_t / mu_t` (`ratio_tol = 1e-9`) is gated only on
  ratio-conditioned rounds, where the normalization is numerically meaningful.
- **Realized stability utilization** is the descriptive quantity
  `abs(R_c - R_r) / A`, computed downstream from frozen seed-level route
  metrics (`derive_utilization.py`, or automatically in the derived stage). It
  measures how much of the sharp stability budget a controlled path realizes;
  it is not a theorem and not a proof of sharpness. When the alignment budget is
  numerically zero the value is NaN with `utilization_defined = False`, never a
  manufactured 0.

These outputs are not automatically paper-promoted: they remain
`paper_result=false` until a separate human authorization, and they are not a
new primary mechanism. When that authorization exists, `promote_targeted.py`
adds them to the paper candidate under `promotion_scope = targeted_extension`;
the `outputs/full` sources keep `paper_result=false` either way.

## Interpretation boundary

- The experiment is a controlled-simulation diagnostic of route-level
  alignment and structural regret transfer; it does not estimate deployment
  value or real-world policy performance.
- Presentation-only rebuilds do not rerun the scientific experiment.
- Formal full runs remain separate from presentation-only regeneration.

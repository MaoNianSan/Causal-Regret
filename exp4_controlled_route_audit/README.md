# Experiment 4: Controlled Route Alignment and Evidence-Qualified Audit

Experiment 4 is a controlled synthetic audit. It separates the population alignment of an operational route from the reliability of an audit based on limited source-grounded comparison evidence.

Its evidence chain is:

$$
\text{controlled route boundary}
\longrightarrow
\text{finite/selective audit evidence}
\longrightarrow
\text{affine calibration diagnostics}.
$$

This experiment does **not** establish a general proxy-impossibility theorem, identify a real-world causal attribution rule, or treat calibration improvement as proof of route validity.

## Scientific modules

### Module A: controlled route boundary

The simulator provides the complete structural loss map

$$
L_t^c(a)=L^c(a;S_t),
$$

and constructs simulator-only full-map routes:

- `arrival_time` — arrival-clock assignment with equal aggregation and last observation carried forward;
- `history_surrogate` — an anonymous observable-history route;
- `proxy_label` — partial source labels plus fixed proxy attribution;
- `source_bound` — the source-binding reference.

The primary estimand is

$$
d_ {\mathrm{pop,raw}}^r
=
\frac{1}{T-W}
\sum_{t=W}^{T-1}
\max_{a<b}
\left|G_t^r(a,b)-G_t^c(a,b)\right|.
$$

The full-map routes are diagnostics. They are not online methods that observe counterfactual action maps.

### Module B: audit reliability

The primary audited route is `proxy_label` with route-label rate `0.30` and attribution-proxy noise standard deviation `0.25`. Audit evidence is generated independently at rates `0.10`, `0.30`, `0.50`, and `1.00`.

The main audit designs are:

1. MCAR, unweighted;
2. ambiguity-biased inclusion, unweighted;
3. ambiguity-biased inclusion, inverse-probability weighted with the known simulated inclusion probability.

Pair-specific affine calibration uses five contiguous temporal folds. The calibrated population target is conditional on the fold-specific fitted maps. Pairwise calibrated signals are not converted into a policy or a coherent corrected loss map.

## Information and interpretation boundaries

- Structural loss maps and realized noisy feedback are stored separately.
- The observation clock is extended to `T + maximum_candidate_delay`, so every source outcome completes route processing.
- Route-construction labels and audit-evidence labels use independent random streams.
- The ambiguity score is based on label-blind observable attribution weights and does not read latent states, structural gaps, route-label masks, or future outcomes.
- Source identity does not automatically identify counterfactual action gaps in ordinary logs. The controlled design supplies those gaps directly.
- `effective_labelled_sample_size` and `labelled_support_coefficient` quantify evidence support. They are not probabilities of validity or confidence levels.
- Fast outputs are never paper eligible.
- Full execution does not perform paper promotion.

## Install

```powershell
python -m pip install -r requirements.txt
```

Parquet output is part of the frozen artifact contract, so `pyarrow` is required.

## Run

```powershell
# Smoke test and scientific invariant check
python main.py fast

# Formal run: 30 shared Module A seeds and 200 Module B replications
python main.py full
```

The current v1 runner is deterministic and sequential. `--n-jobs` is accepted and recorded for interface stability but does not alter execution.

Each command creates an isolated directory:

```text
outputs/runs/<run_id>/
```

with:

```text
raw/trajectories/
raw/route_maps/
derived/
figures/pdf/
figures/png/
figures/data/
figures/metadata/
tables/
checks/
reports/
logs/
```

## Paper promotion

A passed full run remains:

```text
paper_result=false
```

Promotion is a separate explicit action:

```powershell
python promote_results.py --run-dir outputs/runs/<full_run_id> --approve-claims
```

The `--approve-claims` flag confirms that manuscript claims remain within the frozen experimental scope. Promotion checks engineering status, scientific status, primary runs, reconstructable figures and tables, current result schema, and claim scope.

## Main paper artifacts

```text
figures/pdf/fig_exp4_route_alignment_and_audit.pdf
tables/tbl_exp4_audit_reliability.tex
reports/exp4_run_summary.md
```

The main figure contains:

- (a) route-alignment boundary;
- (b1) raw-defect estimation bias;
- (b2) raw-defect estimation RMSE;
- (c) calibration controls.

All figure scripts read frozen derived files. They do not refit models or recompute scientific estimands.

## Hard scientific invariants

The run stops unless:

$$
d_{\mathrm{pop,raw}}^{\mathrm{source\_bound}}<10^{-12},
$$

and, for all primary proxy-noise values,

$$
q_{\mathrm{route}}=1
\Longrightarrow
d_{\mathrm{pop,raw}}^{\mathrm{proxy\_label}}<10^{-12}.
$$

It also checks complete 45-pair support, positive proxy-attribution mass, valid inclusion probabilities, honest temporal cross-fitting, independent route/audit streams, reconstructable population targets, and equality of the full-label Proxy-label learner and Source-bound learner action traces.

## Cleaning

`clean.py` is independent and is never called by the runner:

```powershell
python clean.py
```

Type `CLEAN` when prompted.

## Legacy migration

The old directory `exp4_proxy_sufficiency_impossibility` and schema `legacy_exp4_v1` are superseded. See `MIGRATION_RECORD.md`. Legacy outputs cannot be used for the new action-gap estimands or paper promotion.

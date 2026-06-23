# Experiment 3 — Offline recoverability of a constructed 6h target in KuaiRand logs

## Scope and claim boundary

Experiment 3 is an **offline logged-support diagnostic**, not an online
recommendation-policy evaluation.  A source event is a standard-feed video
exposure.  Its target is the same user's observed engagement in the subsequent
six hours of the **same standard-log stream**:

\[
V_{u,t}^{(6h)}=0.5\,\mathrm{long\_view}+1.0\,\mathrm{like}+1.0\,\mathrm{comment}+1.0\,\mathrm{forward}+1.5\,\mathrm{follow},\qquad
Y_{u,t}=\log(1+V_{u,t}^{(6h)}).
\]

This target is deliberately a constructed predictive outcome.  It is **not**
an official KuaiRand utility, a native delayed-feedback label, an identified
causal effect of the source exposure, or an off-policy policy value.

KuaiRand includes randomly exposed videos as a separate intervention regime.
This protocol does not add the main-period random stream to the target because
there is no matched historical random stream used for proxy fitting; adding it
only at evaluation would alter the target between history and main splits.

## Chronology and information interfaces

- `history standard` is used to construct the history target, define the fixed
  category vocabulary, and fit ridge coefficients.
- `main standard` supplies held-out source events, lagged short-term features,
  the constructed 6h target, and evaluation support. Main-period proxy features are restricted to completed history and earlier main bins; no full-main fallback statistic is used.
- The category vocabulary contains the 20 most frequent non-missing history
  tags.  The residual `other` bucket is retained in update accounting but is
  never a candidate action.
- The action set available in a daily evaluation bin is support restricted to
  history-defined categories with sufficient main-log target observations in
  that bin.  This is an **evaluation support restriction**, not a claimed
  platform candidate set.
- A pseudo-arrival delay lies in `[6h, 10h]`, after the full 6h outcome window.
  The coupled condition uses only an action-level history target score to rank
  the fixed delay pool.
- At feedback arrival, the carrier action is the **most recent same-user
  standard exposure at or before arrival**.  No future exposure can be used as
  a carrier.

## Methods

| Method id | Information interface | Role in this diagnostic |
|---|---|---|
| `arrival_time_naive` | arrival-time carrier | Operational mismatch baseline |
| `partial_source_label_q10/q30/q50` | partial source labels + carrier fallback | Recoverability regimes |
| `short_term_ridge_proxy` | history-fitted ridge over lagged short-term signals | Main proxy route |
| `short_term_composite_surrogate` | lagged fixed composite | Main surrogate route |
| `history_ewma_ridge_proxy` | history EWMA plus lagged signals | Appendix proxy robustness check |
| `history_mean_static` | completed-history action mean only | Diagnostic control for stable category persistence |
| `source_aware_reference` | current source-bin target | Offline reference only |

The `q` routes use deterministic event-level masks.  A labelled outcome updates
its source action, while an unlabelled outcome updates its arrival-time carrier.
Thus `q=0` equals the arrival-carrier route and `q=1` equals source-labelled
empirical updating.

## Evaluation and uncertainty

At each daily epoch, a route ranks the same support-restricted category set.
The primary metric is:

\[
\mathrm{ranking\_regret}_b =
\max_{a\in\mathcal A_b^{\mathrm{support}}} \bar Y_{b,a}
- \bar Y_{b,\hat a_b}.
\]

The source-aware route is a reference that sees the current source-bin target
means; it is never interpreted as deployable.

Uncertainty uses user-cluster resampling conditional on the observed calendar
window. The procedure replays arrival/carrier updates under sampled user
weights. Partial-label routes pair each draw with one event-level mask
trajectory sampled from a finite bank (3 in fast mode; 30 in full mode).
History-fitted ridge coefficients, proxy score paths, and support masks remain
fixed. This is a conditional diagnostic interval, not a full-retraining or OPE
confidence interval. The paired arrival-mechanism CSV audit uses the same
user-bootstrap weights across independent and coupled conditions. The run also
reports oracle top-action diversity and switch frequency, and a paired
`ST ridge` versus `History mean` comparison; the latter is the required control
for claims about incremental dynamic proxy information.

## Input files

Place the required original files under `inputs/KuaiRand-1K/data/`:

```text
log_standard_4_08_to_4_21_1k.csv
log_standard_4_22_to_5_08_1k.csv
video_features_basic_1k.csv
```

The random log and other feature files are optional audit inputs and are not
required by the primary v5 run.

## Run

```bash
python code_check.py
python reproduce_fast.py --n-jobs 12
python self_check.py --mode fast
```

Without the original KuaiRand files, fast mode creates a deterministic synthetic
fixture for interface testing only.  Such output is always `paper_result=false`.

```bash
python reproduce_full.py --n-jobs 24
python self_check.py --mode full
python self_check.py --mode full --promote-paper-result
python build_upload_packages.py
python verify_release_package.py
```

Full mode is blocked when the required real inputs are absent.

## Outputs

```text
outputs/<mode>/
  raw/
  processed/
  summaries/
  tables/
  figures/pdf/
  figures/png/
  figures/data/
  figures/metadata/
  metadata/
  checks/
  reports/
```

Every figure has PDF, PNG, source CSV, and metadata JSON. Input SHA-256 hashes,
config hash, run id, and artifact checksums are retained in the output manifest.
A successful full-data promotion regenerates every active figure bundle with
`paper_result=true`. Active figures are the main recoverability figure and the
appendix horizon-eligibility diagnostic. Source-label sensitivity is emitted as
`tbl_app_exp3_source_label_sensitivity.csv`, including the absolute expected
number of labelled outcomes; it is intentionally not a monotonicity-looking
curve. The matched-mechanism contrast remains an audit CSV only. Additional
audit summaries include `paired_mechanism_contrast.csv`,
`paired_effect_vs_history_mean_static.csv`, and
`oracle_action_dynamics_summary.csv`.

Fast outputs are never paper results. Only promoted full outputs with
`paper_result=true` may be cited from LaTeX.

Paper-facing outputs are limited to:

```text
outputs/full/figures/pdf/fig_exp3_long_term_recoverability.pdf
outputs/full/figures/pdf/fig_app_exp3_horizon_eligibility.pdf
outputs/full/tables/tbl_app_exp3_proxy_static_control.csv
outputs/full/tables/tbl_app_exp3_source_label_sensitivity.csv
outputs/full/tables/tbl_app_exp3_proxy_score_quality.csv

## GitHub packaging notes

### Purpose

Offline recoverability diagnostic for constructed delayed targets in sequential recommendation logs.

### Directory layout

- `src/`: shared artifact and runner support.
- `inputs/`: local-only KuaiRand placement notes; raw data files and archives are ignored.
- `ipy/`: GitHub-facing result-check notebook.
- `outputs/`: committed lightweight summaries, figures, tables, checks, metadata, reports, and manifests; processed/raw intermediates are ignored.
- `docs/`: experiment specification, metric specification, and paper-interface notes.
- `tests/`: lightweight temporal contract checks.

### Input data requirement

Full reproduction requires the KuaiRand-1K files listed above under `inputs/KuaiRand-1K/data/`, obtained from the official source under the dataset license. These files are not redistributed.

### How to run fast validation

Use `python reproduce_fast.py --n-jobs 12`, then `python self_check.py --mode fast`. Fast mode may use a deterministic synthetic fixture when real data is absent and is not paper-eligible.

### How to run full reproduction

Use `python reproduce_full.py --n-jobs 24`, then the documented full self-check and promotion commands. Full mode requires external KuaiRand files and was not run during final packaging.

### How to inspect existing results

Open `ipy/exp3_result_check.ipynb` or inspect `outputs/full/summaries/`, `outputs/full/figures/`, `outputs/full/tables/`, `outputs/full/checks/`, and `release_manifest.*`.

### Expected outputs

Expected GitHub-facing outputs are recoverability figures, appendix tables, summary CSV files, bootstrap/audit summaries, checks, metadata, reports, and release manifests.

### What is committed to GitHub

Source code, README/docs, notebooks, tests, manifests, lightweight summaries, figures, tables, checks, metadata, and reports.

### What remains local and why

KuaiRand raw files, downloaded archives, processed parquet files, raw outputs, and large audit intermediates remain local because of size and dataset-license constraints.
outputs/full/summaries/paired_effect_vs_history_mean_static.csv
```

Retired/audit-only figure interfaces are:

```text
fig_app_exp3_arrival_mechanism_contrast
fig_app_exp3_source_label_coverage
fig_app_exp3_horizon_saturation
```

The upload archives exclude raw KuaiRand inputs, user-level raw logs, full raw
event-level outputs, large temporary CSVs, cache directories, legacy synthetic
fixture outputs, and retired figure bundles. The reproducibility archive instead
includes input-path and SHA-256 templates plus instructions for obtaining the
KuaiRand data separately.

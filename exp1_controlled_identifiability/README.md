# EXP1: Controlled source-binding identifiability simulation

## Experimental purpose

EXP1 is a **contextual controlled simulation** for the source--intervention
binding claim. It is not a comparison against an oracle with access to an
unobserved latent state. At each decision time,

\[
S_t=0.98S_{t-1}+\varepsilon_t,\qquad X_t=S_t+\xi_t,
\]

where the Gaussian AR(1) state is deliberately **unclipped**. Every learner
receives the same decision-time context \(X_t\). The realised loss is

\[
\ell_t(a)=(S_t-\mu_a)^2.
\]

The reported quantity is excess conditional risk relative to the
information-consistent oracle

\[
a_t^\star(X_t)=\arg\min_a\mathbb E[\ell_t(a,S_t)\mid X_t].
\]

The central contrast is therefore a correctly restored source tuple
\((X_s,A_s,Y_s)\) versus arrival-time misassignment \((X_t,A_t,Y_s)\).

## Delay settings

`geometric_matched_15`, `mixture_matched_15`, and
`state_structural_matched_15` are the primary matched comparison. For each
seed, state/context paths and policy-independent delay paths are generated
before learning and shared across every method and feedback regime. Each path
is calibrated to the realised, uncensored, finite-horizon mean delay of 15.

`action_structural_stress` is intentionally action-dependent and can therefore
change under a learner's policy. It is a stress test only and is excluded from
any same-mean-delay claim.

`proxy_good_matched_15` and `proxy_bad_matched_15` share their state, context,
and delay paths. They differ only in the additional proxy-observation noise
(0.20 versus 4.00). The proxy-quality figure is therefore a controlled
quality contrast, not a comparison across different environments.

## Methods and information contracts

All arrival-time baselines update **once per arrived source outcome**. No method
is allowed to convert a batch of arrivals into a single effective observation.
Exact labelled and soft-attribution updates both contribute total feedback mass
one per observed outcome.

### Gaussian-integrated EM

The technical identifier `causal_em` is displayed as **Gaussian-integrated
EM**. Under state-structural delay it computes the observable-information
prior

\[
P(D=d\mid Z_s)\approx
\int p(s)(1-p(s))^d p(s\mid Z_s)\,ds,
\]

using 15-point Gauss--Hermite quadrature at the learner's binned source feature.
It is not labelled “correctly specified”: the quadrature/binned observable
model remains an explicit modelling approximation.

`causal_em_misspecified` is displayed as **Stationary-geometric EM**. It drops
source-state dependence deliberately and is an ablation of the delay model,
not an information-impossibility result.

### Proxy learner

`proxy` filters decision-time proxy observations into \(\widehat S_t\). Its
action selection, labelled source updates, and unlabelled candidate updates all
use the **same saved source-time Kalman feature** \(\widehat S_s\). It never
uses environment-provided `src_x` in its labelled branch. The run output records
`labelled_feature_alignment_max`, which must be zero up to numerical precision.

## Run commands

```powershell
# Compile all scripts and execute the complete 264-combination smoke design.
python code_check.py

# 3 seeds, T=5000, all 792 fast combinations and registered outputs.
python reproduce_fast.py
python self_check.py --mode fast

# 30 seeds, T=5000, full raw schedule/arrival/step logs.
python reproduce_full.py
python self_check.py --mode full
```

`fast` and `full` differ only in seed count. Neither execution is automatically
a paper result; manuscript use requires review of the completed outputs.

## Self-check requirements

`self_check.py` validates:

- contextual regret comparator and common decision-time context;
- pre-generated shared paths and realised matched-delay calibration;
- isolation of policy-dependent action-structural delay;
- one feedback unit per observed source outcome;
- posterior-derived attribution metrics;
- Gaussian-integrated versus stationary-geometric EM contracts;
- zero EM/proxy labelled feature-space discrepancy;
- a real high/low proxy-error contrast; and
- all four registered figure bundles.

## Registered outputs

- `fig_exp1_validity_boundary`: contextual causal-regret mechanism chain;
- `fig_exp1_same_mean_delay`: realised mean delay versus regret under primary
  matched mechanisms;
- `fig_exp1_attribution_diagnostics`: posterior mass/top-1 recovery over all
  unlabelled arrivals;
- `fig_exp1_proxy_quality`: controlled proxy-state error versus regret.

## GitHub packaging notes

### Purpose

Controlled identifiability simulation for source-time binding under delayed feedback.

### Directory layout

- `src/`: experiment implementation and artifact helpers.
- `ipy/`: GitHub-facing result-check notebook.
- `outputs/`: saved lightweight figures, tables, summaries, checks, and metadata.
- `runlogs/`: saved command logs from previous runs.
- `docs/`: paper-interface notes.

### Input data requirement

No external raw dataset is required for the committed saved-output inspection. Any local raw or regenerated intermediate files should remain outside GitHub-tracked output categories.

### How to run fast validation

Use `python reproduce_fast.py` followed by `python self_check.py --mode fast`.

### How to run full reproduction

Use `python reproduce_full.py` followed by `python self_check.py --mode full`. This is a full experiment rerun and was not executed during final packaging.

### How to inspect existing results

Open `ipy/exp1_result_check.ipynb` or inspect `outputs/full/figures/`, `outputs/full/tables/`, `outputs/full/summaries/`, and `output_manifest.md`.

### Expected outputs

Expected GitHub-facing outputs are summary CSV files, figure PDF/PNG files, figure source CSV files, metadata JSON files, checks, and tables.

### What is committed to GitHub

Source code, README/docs, notebooks, run logs, manifests, and lightweight saved outputs.

### What remains local and why

Runtime caches, raw regenerated logs, intermediate folders, and temporary check artifacts remain local because they are reproducible or too noisy for repository review.

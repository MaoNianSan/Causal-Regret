# Experiment 4: Source-Label Sufficiency and Proxy-Only Recovery Limitation

Experiment 4 is a **controlled synthetic stress test**. It is not logged-data evidence, a real-world RCT, a platform-utility study, a leaderboard of proxy algorithms, or an information-theoretic impossibility theorem.

Its narrow evidence chain is:

\[
\text{measurement-induced proxy distortion}
\rightarrow
\text{partial source-label recovery}
\rightarrow
\text{limits of replacing source binding with a fixed proxy-only recovery rule}.
\]

## Information Protocol

At round \(u\), each route chooses \(A_u\) before processing feedback arriving at \(u\). A source outcome from \(s\) arrives at \(u=s+\tau_s\). Within each seed × setting, methods share the latent-state path, potential-loss path, delay path, and coarse observable decision-time context.

- `arrival_time_naive`: assigns anonymous arrivals to the current action and context.
- `observable_history_surrogate`: uses exponentially discounted anonymous arrival history in the observable context; it receives no source labels.
- `proxy_label_recovery`: uses exact retained source labels; for anonymous arrivals, it distributes loss over feasible past sources using **stored observable proxy history**, a fixed RBF similarity kernel, and a fixed recency prior.
- `source_labelled_reference`: updates the exact source action and source context after every arrival. It is an online information-interface reference, not a label-scarce deployable method.
- `proxy_noisy_oracle_diagnostic` and `proxy_oracle_diagnostic`: diagnostic controls only.

The proxy-recovery route is deliberately transparent rather than optimized: its bounded window is `max_delay=20`, kernel bandwidth is `0.55`, and recency decay is `0.035`. Therefore Exp4 can support statements about this information interface and this fixed recovery route; it cannot establish that every possible learned or calibrated proxy-only method must fail.

The source-ID retention indicator is generated at source time and revealed only on arrival. At \(q=1\), `proxy_label_recovery` and `source_labelled_reference` must have identical complete action traces; this is checked by a per-seed SHA-256 action-trace audit in both the source-label sweep and every \(q=1\) cell of the \(q\times\sigma\) phase grid.

## Primary Outcome

The primary outcome is post-warmup structural causal regret:

\[
\frac{1}{T-250}\sum_{t=251}^{T}
\left[\ell(A_t,S_t)-\min_a\ell(a,S_t)\right].
\]

The first 250 rounds remain in online learning history and are excluded only from the primary aggregate.

## Run

```powershell
python -m pip install -r requirements.txt

# Fast interface and direction check: 3 shared seeds.
python reproduce_all.py --mode fast --n-jobs 16

# Paper-eligible run: 30 shared seeds and 2,000 percentile-bootstrap resamples.
python reproduce_all.py --mode full --n-jobs 32
```

Each invocation creates `outputs/runs/<mode>_<UTC timestamp>_<id>/`.

## Paper-Facing Figures

- `fig_exp4_recoverability_boundary.pdf`
  - (a) diagnostic proxy-state error versus loss-map distortion;
  - (b) causal regret against source-label retention at fixed \(\sigma=0.25\), with arrival-time and history-surrogate horizontal references;
  - (c) raw arrival–oracle normalized recovery over the \(q\times\sigma\) grid. The colour display uses `[0,1]`, but stored values are not clipped. In panel (c), sigma perturbs only the attribution proxy used to weight candidate historical sources. The decision-time context proxy is held fixed at sigma = 0.25. A value of one in the arrival-oracle normalized recovery map corresponds to the latent action oracle, not to the source-labelled online reference.

  Panels (b) and (c) use the `structural_high` setting with \(\beta=2.00\). The phase map tests whether precision of the specified proxy route can replace missing source labels; it is not a general proxy-algorithm benchmark.

- `fig_app_exp4_delay_state_coupling.pdf`
  - (a) source-arrival ranking reversal against coupling;
  - (b) source-binding advantage, `arrival-time regret − source-labelled regret`.

  beta = 0 denotes no additional delay-state association. It does not imply zero delay or zero source-arrival mismatch. The source-binding advantage is positive across the tested coupling settings, but is not claimed to increase monotonically with beta.

The appendix table `tbl_app_exp4_source_labelled_recovery.csv` reports

\[
\frac{R_{\mathrm{arrival}}-R_{\mathrm{route}}}
{R_{\mathrm{arrival}}-R_{\mathrm{source\ labelled\ reference}}},
\]

for which \(q=1\) is one when the action-trace audit passes.

## Fast/Full Boundary

Fast mode executes the complete condition grid with three shared seeds and produces point estimates only. Full mode uses 30 shared seeds and 2,000 seed-level percentile-bootstrap resamples. Full comparisons report paired confidence intervals only; no p-values are produced.

Only a passed full run with complete figure bundles, `self_check`, and `code_check` can set `paper_result=true`.

## GitHub Packaging Notes

### Purpose

Synthetic proxy-sufficiency and source-label recoverability stress test.

### Directory layout

- `*.py`: simulator, policy, aggregation, plotting, and manifest scripts.
- `ipy/`: GitHub-facing result-check notebook.
- `outputs/runs/`: saved lightweight run outputs, figures, tables, summaries, checks, metadata, logs, and reports.
- `input/`: optional local-only placement holder.

### Input Data Requirement

No external raw dataset is required. The experiment is synthetic and configured from repository code.

### How to Run Fast Validation

Use `python reproduce_all.py --mode fast --n-jobs 16`.

### How to Run Full Reproduction

Use `python reproduce_all.py --mode full --n-jobs 32`. This is a full experiment rerun and was not executed during final packaging.

### How to Inspect Existing Results

Open `ipy/exp4_result_check.ipynb` or inspect the newest saved run under `outputs/runs/`, especially `figures/`, `tables/`, `summaries/`, `checks/`, `logs/`, and `reports/`.

### Expected Outputs

Expected GitHub-facing outputs are run-specific figure bundles, summary CSV files, appendix tables, validation checks, metadata, logs, and audit reports.

### What Is Committed to GitHub

Source code, README, notebook, lightweight saved run outputs, figures, tables, summaries, checks, metadata, logs, and reports.

### What Remains Local and Why

Runtime caches, raw/intermediate folders, and temporary files remain local because they are reproducible support artifacts rather than GitHub-facing results.

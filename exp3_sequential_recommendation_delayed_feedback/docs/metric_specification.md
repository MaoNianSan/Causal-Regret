# Exp3 metric specification

## Scope

Exp3 is an **offline logged-support recoverability diagnostic**. It does not
estimate a native KuaiRand delayed label, an off-policy value, an online-policy
regret, or a causal effect of a recommendation action.

## Constructed target

- **Primary outcome**: `long_value_log = log1p(future_value_6h)`.
- **future_value_6h**: for a source exposure at time \(t\), the weighted sum of
  the same user's standard-log `long_view`, `like`, `comment`, `forward`, and
  `follow` events in \((t,t+6\mathrm{h}]\), with weights
  \(0.5,1.0,1.0,1.0,1.5\), respectively.
- **Eligibility**: an event is evaluated only when the same user remains
  observed in that standard-log split through the whole 6h window.
- The target is therefore a constructed future-engagement prediction target; it
  is not attributed to the source exposure as an identified causal outcome.

## Action abstraction and evaluation

- **Action abstraction**: the 20 most common non-missing history-standard tags.
  The residual `other` bucket is retained for feedback accounting but excluded
  from candidates.
- **Support restriction**: a day/action cell enters comparison only if it has
  at least `sequential_min_cell_count=50` valid source events. This restricts
  observed support; it is not a platform candidate generator.
- **Primary metric**:
  \[
  \operatorname{ranking_regret}_b=
  \max_{a\in\mathcal A_b^{\mathrm{support}}}\bar Y_{b,a}
  -\bar Y_{b,\hat a_b}.
  \]
  The reported statistic is the mean across eligible daily bins.
- **Top-k overlap**: overlap with the source-aware reference ordering at
  `k=10`.

## Information routes

- **Arrival carrier**: at pseudo-arrival, assign feedback to the most recent
  same-user standard exposure at or before arrival. Future exposures are never
  eligible carriers.
- **Partial labels**: an event-level mask selects a source update with
  probability \(q\); unlabelled outcomes update the arrival carrier.
- **Proxy routes**: ridge coefficients use only history-standard target cells.
  Main scores use completed history and earlier main source bins only. In
  particular, no full-main-period proxy mean or composite mean is allowed as a
  fallback feature.

## Pseudo-arrival mechanism

Pseudo-delay is between 6h and 10h, after the full target window. The primary
condition deterministically couples the matched delay pool to a completed-
history action-level target signal. The independent condition uses the same
marginal delay pool without such coupling. These are semi-synthetic sensitivity
conditions, not estimates of platform arrival dynamics.

## Uncertainty

- Point estimates for partial-label routes average three event-level mask
  trajectories in fast mode and 30 in full mode.
- The reported percentile interval is a **user-cluster resampling interval**
  conditional on the observed calendar window, the fixed history-fitted proxy,
  and the fixed support mask.
- Each bootstrap draw for a partial-label route is paired with one independent
  event-level mask trajectory sampled with replacement from the finite mask
  bank. This captures the designed label-availability variation without an
  infeasible nested re-scan of all source events for every bootstrap draw.

The interval should not be interpreted as an OPE confidence interval or as a
generalization interval over unobserved platform time periods.


## Static-control and label-availability reporting

`history_mean_static` is a required diagnostic control. It ranks action
categories using only completed-history 6h target means. It uses no main-period
short-term feature, pseudo-arrival message, or source label. The required paired
comparison reports:

\[
\Delta_{m,\mathrm{static}}=R_{\mathrm{static}}-R_m,
\]

where positive values favor route \(m\). A percentile interval spanning zero
does not establish incremental dynamic proxy value beyond stable category
persistence.

Partial-label results are reported in a table with both \(q\) and the expected
absolute number of labelled source outcomes. The table is a high-volume
finite-sample sensitivity diagnostic; it does not support a monotonicity claim
or a statement that a given label fraction is generally sufficient.

The appendix horizon figure reports right-censoring rate, not mean target
magnitude. It documents the availability tradeoff across prespecified horizons
and does not select the 6h horizon post hoc.

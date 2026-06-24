# EXP1 controlled source-binding validity design

## Information structure and estimand

At every decision time, all learners observe the same public context. The
latent state remains unavailable to non-reference learners. Regret is computed
relative to the action that minimises conditional loss under the public context,
not relative to a full-state oracle. This keeps unavoidable partial
observability separate from delay-induced attribution distortion.

## Primary delay comparison

The primary matched settings pre-generate and share state, context, and
policy-independent delay paths within each seed. Their realised finite-horizon
observed mean delay is calibrated to approximately `15`.

The policy-dependent action-structural setting is retained as a stress test,
not as part of the matched-delay main claim.

## Recovery routes

- Source-labelled updates use the generating source-time feature and action.
- Soft attribution uses posterior mass across candidate source events.
- Proxy-state updates use the saved source-time filtered proxy feature for both
  action selection and labelled/unlabelled updates.
- Gaussian-integrated EM integrates delay likelihood over the observable-state
  posterior. The stationary-geometric EM is a deliberate ablation.

## Interpretation boundary

EXP1 tests the validity of source binding under controlled delay. It does not
assert universal algorithm superiority, universal unlabelled recovery, or a
fixed difficulty ordering among all matched delay mechanisms.

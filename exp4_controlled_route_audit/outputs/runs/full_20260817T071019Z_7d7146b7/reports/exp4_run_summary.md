# Experiment 4 v3 Run Summary

- Run ID: `full_20260817T071019Z_7d7146b7`
- Run tier: `full`
- Result schema: `exp4_controlled_route_audit_v3`
- Engineering status: `PASS`
- Scientific status: `PASS`
- Paper promotion: `NOT_RUN`
- Paper result: `false`

## Run lineage

- Lineage schema: `exp4_run_lineage_v1`
- Simulation execution mode: `FRESH`
- Simulation source run: `NONE`
- Downstream execution mode: `REBUILT_FROM_OWN_SIMULATION`
- Downstream source run: `NONE`
- Created from commit: `23199c4827c06f76d1d9a7a4fc39e56e21eb26b8`
- Exp4 worktree clean at start: `True`
- Formal Full clean-worktree required: `True`
- Source unchanged during run: `False`

## Core diagnostics

- Maximum q_route=1 mean pairwise gap discrepancy: 0.000e+00
- Maximum q_route=1 mean round-max gap defect (legacy v2): 0.000e+00
- Audit bias range: [-0.0000, 0.0316]
- Audit RMSE range: [0.0000, 0.0319]
- Module C estimability range: [1.000, 1.000]

## Interpretation boundary

- Module A estimates a controlled population route-alignment boundary; the v3 primary estimand is the pair-average gap discrepancy D_pair.
- Module B separates the pair-average population discrepancy from finite/selective audit reliability; all audit designs target the same d_i_pair.
- Module C evaluates discrepancy reduction inside a prespecified affine family; it does not create a corrected policy or certify route validity.
- Known simulated IPW probabilities do not establish validity under an unknown real-world inclusion mechanism.

FULL_RUN_EXECUTED=YES
PAPER_PROMOTION_EXECUTED=NO
GIT_COMMIT_EXECUTED=NO
GIT_PUSH_EXECUTED=NO

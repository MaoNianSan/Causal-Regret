# Experiment 4 v2 Run Summary

- Run ID: `full_20260807T045219Z_7eeb2a31`
- Run tier: `full`
- Result schema: `exp4_controlled_route_audit_v2`
- Engineering status: `PASS`
- Scientific status: `PASS`
- Paper promotion: `PASS`
- Paper result: `true`

## Run lineage

- Lineage schema: `exp4_run_lineage_v1`
- Simulation execution mode: `FRESH`
- Simulation source run: `NONE`
- Downstream execution mode: `REBUILT_FROM_OWN_SIMULATION`
- Downstream source run: `NONE`
- Created from commit: `7915d9f10d3f70094c057f75655f791b44f9997c`
- Exp4 worktree clean at start: `True`
- Formal Full clean-worktree required: `True`
- Source unchanged during run: `True`

## Core diagnostics

- Maximum q_route=1 population defect: 0.000e+00
- Audit bias range: [-0.0001, 0.1032]
- Audit RMSE range: [0.0000, 0.1041]
- Module C estimability range: [1.000, 1.000]

## Interpretation boundary

- Module A estimates a controlled population route-alignment boundary.
- Module B separates population defect from finite/selective audit reliability.
- Module C evaluates discrepancy reduction inside a prespecified affine family; it does not create a corrected policy or certify route validity.
- Known simulated IPW probabilities do not establish validity under an unknown real-world inclusion mechanism.

FULL_RUN_EXECUTED=YES
PAPER_PROMOTION_EXECUTED=YES
GIT_COMMIT_EXECUTED=NO
GIT_PUSH_EXECUTED=NO

# Causal Regret Minimization under Delayed Feedback

This repository contains four complementary experiment directories for the manuscript "Causal Regret Minimization under Delayed Feedback." Each experiment is self-contained and has a distinct scientific role; they are not a shared benchmark suite with a common estimand.

## Repository scope

| Experiment | Directory | Scientific role | Main evidence | Formal rerun status |
|---|---|---|---|---|
| Exp1 | `exp1_alignment_transfer` | Controlled alignment and regret transfer | Full structural maps + scalar learner | Active, no changes to scientific fingerprint |
| Exp2 | `exp2_real_delayed_conversion_logs` | Attribution sensitivity in delayed-conversion logs | Fixed delayed-conversion log | Active, canonical implementation in `exp2_core` |
| Exp3 | `exp3_sequential_recommendation_delayed_feedback` | Logged-support score/gap/ranking recovery | KuaiRand recommendation logs | Not modified in this cleanup pass |
| Exp4 | `exp4_controlled_route_audit` | Route alignment and evidence-qualified audit | Controlled route/audit simulation | Provenance normalization completed, new Full required |

## Claim boundaries

- Exp1 is responsible for regret transfer, route validity diagnostics, and learner consequence evidence.
- Exp2 evaluates attribution sensitivity and does not attempt to identify a correct attribution rule, measure ROI, or estimate policy value.
- Exp3 is focused on logged-support ranking and gap recovery, not off-policy evaluation or deployment value.
- Exp4 evaluates controlled route-alignment evidence, audit reliability, and calibration-family controls; it does not prove proxy impossibility or treat calibration as policy validity.
- The four experiments do not share a single scientific estimand.

## Quick start

Access the experiment README for detailed commands and run tiers:

- `exp1_alignment_transfer/README.md`
- `exp2_real_delayed_conversion_logs/README.md`
- `exp4_controlled_route_audit/README.md`

This repository does not run Full experiments automatically.

## Data policy

- Exp1 and Exp4 are self-contained and include all tracked scientific artifacts needed for code and documentation.
- Exp2 and Exp3 depend on external input data; raw licensed inputs are not stored in Git.
- Tracked artifacts include source code, test code, configuration, canonical status reports, paper candidate artifacts, and provenance manifests.
- Raw inputs, full raw simulation arrays, caches, temporary logs, local virtual environments, and duplicate debug exports are excluded from tracking.

## Reproducibility and promotion

- `Fast` and `Middle` runs are development tiers and are not paper promotion candidates.
- `Full` runs are separate and only become promotion candidates through explicit, manual approval.
- Provenance manifests and source hashes are used to verify whether a run was produced by a clean, frozen experiment source tree.

## Repository hygiene

See `docs/REPOSITORY_ARTIFACT_AND_CLEANUP_POLICY.md` for rules on what is tracked, what is ignored, and how generated artifacts may be cleaned.

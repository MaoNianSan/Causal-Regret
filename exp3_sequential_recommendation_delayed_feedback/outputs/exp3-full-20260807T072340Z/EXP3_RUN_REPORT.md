# Experiment 3 Run Report

- Run ID: `exp3-full-20260807T072340Z`
- Run tier: `full`
- Input status: `original_kuairand_inputs`
- Input audit status: **PASS**
- Input boundary status: **PASS_WITH_BOUNDARY_QUARANTINE**
- Pipeline execution status: **PASS**
- Independent self-check status: **PASS**
- Archival integrity check status: **NOT_RUN**
- Final engineering status: **PASS**
- Scientific status: **PASS**
- Scientific contract status: **PASS**
- Scientific uncertainty status: **SENSITIVITY_ONLY_ACCEPTED**
- Primary result: **full-sample point estimate**
- Resampling role: **sensitivity_only**
- Displayed range: **percentile_user_cluster_sensitivity**
- Formal confidence interval validated: **false**
- Resampling centering diagnostic: **PASS_WITH_WARNING**
- Full-design support preflight: **READY**
- Full-design support ready: **true**
- Full run recommended: **true**
- Paper promotion eligible: **true**
- Paper result: **true**
- Artifact manifest status: **PASS**
- Code version type: `source_tree_sha256`
- Code version: `030d6bb049591fda35c4e54df090bbc50eb1e12d8482c28cc71dffec7cef6fa0`
- Selected Ridge alpha: **30.0** (history-only rolling temporal validation)

## Uncertainty interpretation

The full-sample estimates are the primary results. The open markers and horizontal ranges summarize the empirical user-cluster resampling distribution. They are sensitivity diagnostics rather than confidence intervals and need not contain the full-sample estimate. The legacy basic-bootstrap reflection is retained only in the audit CSV.

## Selected-action exposure scope

- The selected top-20 action space covers **85.0%** of evaluation exposure mass.
- Within that action space, common-supported action coverage is **92.5%**, reference-pair coverage is **92.1%**, audit-unit coverage is **100.0%**, and mean supported actions are **18.49**.
- The top-20 full-design preflight action space covers **85.0%** of evaluation exposure mass.
- Action, reference-pair, and audit-unit coverage refer to support inside the selected action space; they do not claim coverage of the entire event log.

## Boundary quarantine disclosure

- Raw split non-overlap: **False**
- Timezone rule: `Asia/Shanghai_epoch_day`
- Quarantine policy: `quarantine_events_outside_frozen_split_boundaries`
- History exclusions: **1964** (0.042277%); frozen tolerance 0.100000%.
- Evaluation exclusions: **2195** (0.035808%); frozen tolerance 0.100000%.
- Retained split strictly non-overlapping: **True**

## Data-dependence disclosure

- History: **983 users**, **4643582 source events**; outcome-event reuse rate **99.927337%**; mean/median/p90/max source windows per positive outcome event **206.59 / 136.00 / 475.00 / 3723.00**.
- Evaluation: **1000 users**, **6127661 source events**; outcome-event reuse rate **99.930785%**; mean/median/p90/max source windows per positive outcome event **210.66 / 137.00 / 475.00 / 5534.00**.
- Source-event counts are overlapping target-window diagnostics and are not independent sample sizes.

## Resampling and route-selection structure

- Support-set switch rate: **8.6%**; valid audit-unit change rate: **0.0%**.
- Held-out reference-action switch rate: **46.0%**.
- Route selected-action switch rate: Arrival carrier—misbinding control **49.1%**; Historical mean **6.1%**; Ridge proxy **10.3%**.
- The offset between the resampling distribution and the full-sample statistic reflects highly overlapping target windows, cell-mean changes under user resampling, held-out reference-action switching, the max-type gap statistic, and arrival-carrier selected-action switching. It is not attributed to support-set switching when that rate is zero.

Fast outputs are never paper results. Exp3 remains a logged-support recoverability diagnostic, not OPE or structural causal regret.

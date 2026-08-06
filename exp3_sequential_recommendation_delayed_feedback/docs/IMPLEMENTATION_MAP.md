# Exp3 implementation map

| Frozen object or responsibility | Active implementation |
|---|---|
| Input path resolution, ID normalization, local-time split quarantine | `input_normalization.py` |
| History-only action vocabulary and action-space mass coverage | `preprocess_events.py` |
| 6h target, overlap/reuse audit, pseudo-arrival carrier | `construct_delayed_targets.py` |
| History-only groups, support, near-tie design | `audit_design.py` |
| Canonical names, routes, metrics, aliases, design hash | `design_contract.py` |
| Ridge features, history-only temporal selection, final refit | `ridge_features.py` / `ridge_selection.py` / `route_fitting.py` |
| Immutable user/day/action evaluation arrays | `evaluation_arrays.py` |
| Evaluation-array and point-estimate persistence | `evaluation_artifacts.py` |
| User aggregation, support, score, gap, ranking, and summary | `evaluation_aggregation.py` / `support_metrics.py` / `score_metrics.py` / `gap_metrics.py` / `ranking_metrics.py` / `evaluation_summary.py` |
| Two-fold orchestration facade | `evaluate_recoverability.py` |
| Route action-diversity/equivalence diagnostics | `route_diagnostics.py` |
| User-cluster replication engine | `bootstrap_evaluation.py` |
| Basic/percentile interval definitions and bias audit | `bootstrap_intervals.py` / `bootstrap_summary.py` |
| Formal full-design support preflight | `support_preflight.py` |
| Main score-gap-ranking figure | `plot_contract.py` / `plot_score_panel.py` / `plot_gap_panel.py` / `plot_ranking_panel.py` / `plot_scope_note.py` / `plot_main_results.py` |
| Appendix preflight and arrival-carrier figures | `plot_appendix_results.py` |
| Run-ID and latest-successful/resumable resolution | `run_registry.py` |
| Scientific, engineering, figure, and promotion checks | `self_check.py` / `self_check_helpers.py` |
| Fresh, resume, finalization, and public facade | `pipeline_contract.py` / `pipeline_fresh_run.py` / `pipeline_resume.py` / `run_finalization.py` / `runner.py` / `main.py` |

The active code does not implement source-label sufficiency, OPE, online policy value, structural causal regret, causal action-gap identification, a new model family, or evaluation-driven tuning.

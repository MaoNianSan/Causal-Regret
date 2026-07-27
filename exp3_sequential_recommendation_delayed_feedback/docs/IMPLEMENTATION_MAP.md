# Exp3 implementation map

| Frozen object or responsibility | Active implementation |
|---|---|
| Input path resolution, ID normalization, local-time split quarantine | `input_normalization.py` |
| History-only action vocabulary and action-space mass coverage | `preprocess_events.py` |
| 6h target, overlap/reuse audit, pseudo-arrival carrier | `construct_delayed_targets.py` |
| History-only groups, support, near-tie design | `audit_design.py` |
| Historical mean and compact Ridge routes | `proxy_routes.py` |
| Immutable user/day/action evaluation arrays | `evaluation_arrays.py` |
| Evaluation-array and point-estimate persistence | `evaluation_artifacts.py` |
| Two-fold score, gap, and ranking estimands | `evaluate_recoverability.py` |
| Route action-diversity/equivalence diagnostics | `route_diagnostics.py` |
| User-cluster replication engine | `bootstrap_evaluation.py` |
| Basic/percentile interval definitions and bias audit | `bootstrap_intervals.py` / `bootstrap_summary.py` |
| Formal full-design support preflight | `support_preflight.py` |
| Main score–gap–ranking figure | `plot_main_results.py` |
| Appendix preflight and arrival-carrier figures | `plot_appendix_results.py` |
| Run-ID and latest-successful/resumable resolution | `run_registry.py` |
| Scientific, engineering, figure, and promotion checks | `self_check.py` / `self_check_helpers.py` |
| End-to-end orchestration | `runner.py` / `main.py` |

The active code does not implement source-label sufficiency, OPE, online policy value, structural causal regret, causal action-gap identification, a new model family, or evaluation-driven tuning.

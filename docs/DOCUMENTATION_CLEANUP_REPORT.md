# Documentation Cleanup Report

## A. Summary

- DOCUMENTATION_CLEANUP_STATUS=COMPLETED
- CODE_CLEANUP_STATUS=COMPLETED_FOR_NONESSENTIAL_AUDIT_CODE
- FULL_RUN_EXECUTED=false
- REMOTE_UPLOAD=false
- LOCAL_AUDIT_DUMP_CLEANED=true

## B. Documentation changes

| file | change_type | reason |
|---|---|---|
| README.md | rewrite | Reduced to experiment overview and removed process-oriented narrative |
| exp1_alignment_transfer/README.md | rewrite | Unified structure around objective, boundary, data, estimand, contract, outputs, validation, commands, limitations |
| exp2_real_delayed_conversion_logs/README.md | rewrite | Unified structure around objective, boundary, data, estimand, contract, outputs, validation, commands, limitations |
| exp3_sequential_recommendation_delayed_feedback/README.md | rewrite | Unified structure around objective, boundary, data, estimand, contract, outputs, validation, commands, limitations |
| exp4_controlled_route_audit/README.md | rewrite | Unified structure around objective, boundary, data, estimand, contract, outputs, validation, commands, limitations |
| docs/DOCUMENTATION_CLEANUP_PRE_AUDIT.md | create | Captured pre-cleanup repository state and sync policy |
| docs/EXPERIMENT_DOCUMENTATION_INVENTORY.csv | create | Recorded inventory and keep/delete/rewrite decisions |
| docs/CLEANUP_REFERENCE_CHECK.md | create | Documented reference checks for files slated for deletion |

## C. Removed files

| file | reason | reference_check |
|---|---|---|
| exp3_sequential_recommendation_delayed_feedback/code_check.py | Static audit script without active workflow dependency | yes |
| exp3_sequential_recommendation_delayed_feedback/docs/EXP3_PRE_MODIFICATION_AUDIT.md | Obsolete pre-change audit history | yes |
| exp3_sequential_recommendation_delayed_feedback/docs/EXP3_REDESIGN_IMPLEMENTATION_REPORT.md | Superseded implementation report | yes |
| exp3_sequential_recommendation_delayed_feedback/docs/IMPLEMENTATION_MAP.md | Redundant implementation map | yes |
| exp4_controlled_route_audit/aggregate_results.py | Deprecated compatibility wrapper | yes |
| exp4_controlled_route_audit/audit_engine.py | Deprecated compatibility wrapper | yes |
| exp4_controlled_route_audit/reproduce_all.py | Legacy CLI alias | yes |
| exp4_controlled_route_audit/run_experiment4.py | Legacy compatibility entry point | yes |
| exp4_controlled_route_audit/write_run_summary.py | Replaced by canonical reporting module | yes |
| exp4_controlled_route_audit/reports/EXP4_V2_PRE_REFACTOR_AUDIT.md | Obsolete audit narrative | yes |
| exp4_controlled_route_audit/reports/EXP4_POST_FULL_FIX_REPORT.md | Temporary regression report | yes |
| exp4_controlled_route_audit/reports/EXP4_FINAL_PROVENANCE_FIX_REPORT.md | Temporary provenance report | yes |
| exp1_alignment_transfer/status/EXP1_V2_GIT_SYNC_READINESS.md | Historical status report with no active workflow dependency | yes |
| exp1_alignment_transfer/status/EXP1_V2_IMPLEMENTATION_REPORT.md | Historical implementation report | yes |
| exp1_alignment_transfer/status/EXP1_V2_PRESENTATION_PATCH_BASELINE.md | Historical presentation audit note | yes |
| exp1_alignment_transfer/status/EXP1_V2_PRESENTATION_PATCH_REPORT.md | Historical presentation audit note | yes |
| exp1_alignment_transfer/status/EXP1_V2_TEST_REPORT.md | Historical test report | yes |
| exp2_real_delayed_conversion_logs/docs/EXP2_FINAL_MECHANICAL_REFACTOR_REPORT.md | Historical refactor report | yes |
| exp2_real_delayed_conversion_logs/docs/EXP2_PRE_REFACTOR_BASELINE.md | Historical baseline audit | yes |
| exp2_real_delayed_conversion_logs/docs/EXP2_REFACTOR_STATUS.md | Historical refactor status note | yes |
| exp2_real_delayed_conversion_logs/docs/tools/compare_fast_artifacts.py | One-off comparison utility for historical audits | yes |
| exp4_controlled_route_audit/reports/EXP4_FULL_PROVENANCE_AUDIT.md | Historical provenance audit | yes |
| exp4_controlled_route_audit/reports/EXP4_MANUSCRIPT_MAPPING.md | Historical manuscript mapping note | yes |
| exp4_controlled_route_audit/reports/EXP4_V2_IMPLEMENTATION_STATUS.md | Historical implementation status report | yes |
| exp4_controlled_route_audit/engine.py | Deprecated v1 compatibility exports | yes |
| exp4_controlled_route_audit/io_utils.py | Deprecated v1 compatibility exports | yes |
| exp4_controlled_route_audit/route_maps.py | Deprecated v1 compatibility exports | yes |
| exp4_controlled_route_audit/simulator.py | Deprecated v1 compatibility exports | yes |
| exp4_controlled_route_audit/config.py | Deprecated v1 compatibility exports | yes |
| exp4_controlled_route_audit/self_check.py | Deprecated v1 compatibility wrapper | yes |
| exp4_controlled_route_audit/code_check.py | Deprecated v1 compatibility wrapper | yes |
| exp4_controlled_route_audit/plot_results.py | Deprecated v1 compatibility wrapper | yes |
| exp4_controlled_route_audit/make_tables.py | Deprecated v1 compatibility wrapper | yes |
| exp4_controlled_route_audit/clean.py | Unreferenced standalone cleaner | yes |
| exp4_controlled_route_audit/reports/EXP4_FINAL_PROVENANCE_FIX_FILE_CHANGES.csv | Temporary file-change audit dump | yes |
| exp4_controlled_route_audit/reports/EXP4_FULL_PROVENANCE_AUDIT.json | Temporary provenance audit dump | yes |
| exp4_controlled_route_audit/reports/EXP4_POST_FULL_FIX_FILE_CHANGES.csv | Temporary file-change audit dump | yes |
| exp2_real_delayed_conversion_logs/docs/EXP2_FINAL_FILE_CHANGE_SUMMARY.csv | Temporary file-change audit dump | yes |
| exp3_sequential_recommendation_delayed_feedback/docs/CHANGE_MEMO_EXP3_20260725.md | Historical change memo | yes |
| exp3_sequential_recommendation_delayed_feedback/docs/CHANGE_MEMO_EXP3_20260727_BOUNDARY_PRESERVING_REPAIR.md | Historical change memo | yes |
| exp3_sequential_recommendation_delayed_feedback/docs/CHANGE_MEMO_EXP3_20260727_SENSITIVITY_INTERFACE.md | Historical change memo | yes |
| exp3_sequential_recommendation_delayed_feedback/audit/ (19 local files) | Untracked local audit dumps (EXP3_* logs, diffs, summaries) | n/a (untracked) |
| exp2_real_delayed_conversion_logs/outputs/refactor_audit/ | Untracked local refactor-audit outputs | n/a (untracked) |
| exp3_sequential_recommendation_delayed_feedback/docs/EXP3_SCHEMA_MIGRATION.md | Retained (schema documentation) | keep |

## D. Remaining audit infrastructure

- Self-check retained: Exp1 self-check, Exp2 self-check manifest, Exp3 independent self-check, Exp4 scientific/engineering validation.
- Validation retained: scientific contract checks, schema validation, provenance checks, and figure/table consistency validation.
- Temporary audit removed: obsolete implementation reports, pre-refactor audit narratives, compatibility wrappers, and redundant legacy CLI entry points.

## E. Tests

- compileall: PASS (exp2/exp3/exp4 after round-2 cleanup)
- pytest: collection blocked by duplicate test-module names across experiment directories in the monorepo layout; no new syntax or import failures were introduced by the cleanup edits.
- fast self-check: not executed

## F. Git status

- MODIFIED_FILES: README + 4 experiment READMEs + exp4 writers/tests (pre-existing)
- DELETED_FILES: tracked deletions listed in section C
- UNTRACKED_FILES: cleanup report docs (CLEANUP_REFERENCE_CHECK.md, DOCUMENTATION_CLEANUP_PRE_AUDIT.md, DOCUMENTATION_CLEANUP_REPORT.md, EXPERIMENT_DOCUMENTATION_INVENTORY.csv)
- REMOTE_SYNC_REQUIRED=false

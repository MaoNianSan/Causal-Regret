# Repository Development History (dev-noise classification)

This repository is a **submission companion**: the submission-facing surface
is README.md, REPRODUCE.md, DATA.md, docs/, publication/, scripts/, tests/,
and the four experiment READMEs. Files below that are not part of that surface
are retained as **development history / provenance** and are not referenced by
the submission-facing documents. They are kept so that the decision trail is
auditable; nothing here is deleted by the standardization pass.

## Classification

| File | Class | Why it is kept |
|---|---|---|
| `exp1_alignment_transfer/CHANGE_MEMO_EXP1_002.md` | `DEVELOPMENT_HISTORY` | Exp1 design-change memo (002) |
| `exp1_alignment_transfer/CHANGE_MEMO_EXP1_003.md` | `DEVELOPMENT_HISTORY` | Exp1 design-change memo (003) |
| `exp1_alignment_transfer/CHANGE_MEMO_EXP1_004.md` | `DEVELOPMENT_HISTORY` | Exp1 design-change memo (004) |
| `exp1_alignment_transfer/CHANGE_MEMO_EXP1_005.md` | `DEVELOPMENT_HISTORY` | Exp1 paper-promotion authorization memo (005) |
| `PUBLICATION_REPOSITORY_NORMALIZATION_REPORT.md` | `DEVELOPMENT_HISTORY` | Internal normalization audit report |
| `exp4_controlled_route_audit/reports/EXP4_V3_IMPLEMENTATION_STATUS.md` | `DEVELOPMENT_HISTORY` | Exp4 v3 implementation status report |
| `exp2_real_delayed_conversion_logs/inputs/README.md` | `REQUIRED_PROVENANCE` | Criteo dataset description/citation (referenced by DATA.md) |
| `exp3_sequential_recommendation_delayed_feedback/inputs/README.md` | `REQUIRED_PROVENANCE` | KuaiRand-1K dataset description (referenced by DATA.md) |
| `exp4_controlled_route_audit/outputs/runs/*/reports/exp4_run_summary.md` | `REQUIRED_PROVENANCE` | Frozen run summaries inside canonical/legacy run dirs |
| `LICENSE_SELECTION_REQUIRED.md` | `REQUIRED_PROVENANCE` | License decision is pending human choice; see README License section |
| `docs/EXPERIMENT_IO_CONTRACT.md` | `CURRENT_SUBMISSION_DOC` | Authoritative per-experiment I/O contract |
| `docs/PAPER_RESULTS.md` | `CURRENT_SUBMISSION_DOC` | Canonical result registry |
| `README.md`, `REPRODUCE.md`, `DATA.md`, `CITATION.cff` | `CURRENT_SUBMISSION_DOC` | Landing page, reproduction guide, data guide, citation |
| `exp{1,2,3,4}/*/README.md` | `CURRENT_SUBMISSION_DOC` | Standardized per-experiment READMEs |
| `publication/CR-EXP-OUTPUT-V1/README.md` | `CURRENT_SUBMISSION_DOC` | Publication bundle README |
| `scripts/validate_submission_repository.py` | `CURRENT_SUBMISSION_DOC` | Read-only submission validator |
| `tests/test_submission_repository_contract.py` | `CURRENT_SUBMISSION_DOC` | Submission contract tests |

## Policy

- No `OBSOLETE_DUPLICATE` files were deleted during standardization; legacy
  run directories (e.g. Exp4 v2 `full_20260807T045219Z_7eeb2a31`) are
  retained as provenance and are explicitly excluded from the canonical
  registry.
- `CHANGE_MEMO_*` and `*_REPORT.md` files are historical records. They are not
  linked from the submission-facing READMEs, which point only to the
  current-contract documents.

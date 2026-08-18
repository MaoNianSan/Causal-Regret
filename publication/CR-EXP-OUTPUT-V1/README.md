# CR-EXP-OUTPUT-V1 — Canonical Publication Bundle

This directory is the **paper-facing presentation bundle** for all four
experiments. It is generated from the promoted, frozen scientific derived data
of the canonical runs by the presentation layer
(`presentation_sources.py` + `render_presentation.py`); it is **not** the
scientific output of the experiments and never results from a scientific
rerun.

## What is inside

```text
CR-EXP-OUTPUT-V1/
├── exp1_alignment_transfer/
│   ├── figures/
│   │   ├── main/    (pdf, svg, png, data/, metadata/)
│   │   └── appendix/ (pdf, svg, png, data/, metadata/)
│   ├── tables/      (csv/, tex/, metadata/)
│   ├── manifests/   (presentation_manifest.json, appendix_manifest.json)
│   └── validation/  (presentation_validation.json)
├── exp2_real_delayed_conversion_logs/   (same layout)
├── exp3_sequential_recommendation_delayed_feedback/  (same layout)
└── exp4_controlled_route_audit/         (same layout)
```

- **Main figures** (4): `fig_exp1_alignment_transfer`,
  `figure_exp2_attribution_sensitivity`, `exp3_main_score_gap_ranking`,
  `fig_exp4_route_alignment_and_audit_reliability`. Each main figure has a
  PDF, SVG, PNG, a long-form data CSV
  (`figures/main/data/<id>.csv`) with the columns
  `metric_id,estimand_id,condition_id,series_id,point_estimate,
  interval_lower,interval_upper`, and a JSON metadata record
  (`figures/main/metadata/<id>.json`).
- **Appendix figures**: three or more per experiment (PDF/SVG/PNG + data +
  metadata), enumerated in `manifests/appendix_manifest.json`.
- **Tables**: paper tables in `tables/tex/` (LaTeX) and `tables/csv/` with
  per-table JSON metadata; the `tab_experimental_evidence_map` table maps the
  manuscript evidence items to the bundle artifacts.
- **Manifests**: `presentation_manifest.json` records the source scientific
  run, the scientific generation/config hash, `paper_result=true`,
  `promotion_status=CANONICAL_PUBLICATION`, and keeps
  `scientific_source_lineage` separate from `presentation_source_lineage`.
- **Validation**: `validation/presentation_validation.json` records the
  presentation-layer validation (all `PASS`).

## Canonical source runs

| Experiment | Scientific source (frozen) | Schema |
|---|---|---|
| Exp1 | `exp1_alignment_transfer/outputs/paper_candidate/` (run `exp1_alignment_transfer:full:2026-08-17T06:28:21.157011+00:00`) | v1.2 |
| Exp2 | `exp2_real_delayed_conversion_logs/outputs/paper/exp2-full-20260807T111616+0800/` | — |
| Exp3 | `exp3_sequential_recommendation_delayed_feedback/paper_candidate/` (run `exp3-full-20260807T072340Z`) | — |
| Exp4 | `exp4_controlled_route_audit/outputs/runs/full_20260817T071019Z_7d7146b7/` | `exp4_controlled_route_audit_v3` |

## How to regenerate (no scientific rerun)

```bash
python render_presentation.py render --mode publication --exp all
python render_presentation.py validate --mode publication --exp all
```

See `REPRODUCE.md` (section C) and `docs/EXPERIMENT_IO_CONTRACT.md` for the
full contract. Per-artifact provenance for the manuscript is in
`docs/PAPER_RESULTS.md`.

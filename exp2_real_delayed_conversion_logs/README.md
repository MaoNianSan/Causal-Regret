# Experiment 2: Delayed-Conversion Attribution Sensitivity

Experiment 2 asks a narrow logged-data question:

> Holding eligible conversion journeys and decision-cell support fixed, do alternative attribution routes change source-time credit allocation and the ranking of campaign-day decision cells?

It does **not** estimate causal regret, policy value, ROI, profit, uplift, or a causally correct attribution rule.

## Scientific unit

The decision cell is

```text
(campaign_id, source_date_utc)
```

All primary routes use the same route-independent journey cohort, decision-cell universe, impression denominator, and UID-cluster bootstrap design.

Primary routes:

1. Arrival-time anchor — diagnostic anchor only
2. First click or touch
3. Last click or touch
4. Linear attribution across unique decision cells
5. Time-decay attribution at the decision-cell level

EM soft attribution is appendix-only. The logged attribution field is an audit reference, not complete causal ground truth.

## Main estimands

For route `r` and decision cell `c`:

```text
credited_conversion_mass C_r(c)
allocation_share Q_r(c) = C_r(c) / total route credit
decision_cell_score S_r(c) = C_r(c) / eligible_impression_count(c)
```

Primary metrics:

- aggregate decision-cell allocation TV;
- top-10 decision-cell overlap;
- top-10 ranking displacement;
- Kendall tau-b on common active cell support.

`mean_journey_assignment_tv` is retained as an appendix mechanism diagnostic and is not used as a substitute for aggregate allocation TV.

## Commands

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Fast contract run:

```bash
python main.py fast
```

Fast mode creates a deterministic synthetic fixture, performs 200 UID bootstrap replications, generates the complete figure/table interface, and always records:

```text
run_tier=fast
paper_result=false
```

Full run after placing the Criteo TSV in `inputs/`:

```bash
python main.py full
```

Full mode requires `pyarrow` because the frozen large-table output contract is Parquet. There is no automatic CSV fallback.

Independent promotion of a completed full run:

```bash
python promote.py --run-id <full_run_id>
```

Clean generated outputs:

```bash
python clean.py
```

## Output structure

```text
outputs/<run_id>/
├── run_manifest.json
├── derived/
├── figures/
├── tables/
├── audit/
└── logs/
```

The main paper figure contains:

- Panel (a): allocation TV from the arrival-time diagnostic anchor with top-10 overlap annotations;
- Panel (b): horizontal pairwise allocation-TV dot-and-whisker plot with directly labelled shared top-10 cell counts.

Pairwise allocation TV, top-10 overlap, and Kendall tau-b matrices are appendix outputs. Delay composition is descriptive and remains in the appendix.

## Validation

Run unit and invariant tests:

```bash
pytest -q
```

The checks cover:

- route-independent cohort construction;
- unique UID and unique campaign requirements;
- credit conservation;
- cell-level time decay;
- separation of aggregate allocation TV from journey-level assignment TV;
- allocation normalization;
- deterministic bootstrap results across worker counts;
- location-independent input content identity;
- complete synthetic coverage of all five delay bins;
- consistent bootstrap repetition reporting across audit and manuscript outputs;
- frozen configuration rules.

## Key files

| File | Responsibility |
|---|---|
| `data_io.py` | raw input scan, UTC parsing, candidate staging, input manifest |
| `cohort.py` | common cohort and decision-cell universe |
| `routes.py` | attribution route construction |
| `metrics.py` | allocation, ranking, Kendall, ambiguity metrics |
| `bootstrap.py` | UID-cluster bootstrap |
| `targeted.py` | non-cartesian top-k, window, and support diagnostics |
| `reporting.py` | paper figures, source data, metadata, CSV/LaTeX tables |
| `validation.py` | engineering and scientific gates |
| `runner.py` | staged fast/full orchestration |
| `promote.py` | independent paper promotion |

The detailed frozen specification is in `docs/EXP2_PROGRAMMING_MEMO.md`.

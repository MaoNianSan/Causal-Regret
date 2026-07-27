# Exp2 implementation validation report

## Scope

This report covers the corrected `exp2_real_delayed_conversion_logs` package. It validates the engineering and scientific contracts on the deterministic synthetic fast fixture. The protected real Criteo input was not included in the uploaded package, so this report does not claim a real-data or paper-eligible result.

## Implemented corrections

- Replaced the main figure's right-hand scatter map with a fixed-order horizontal pairwise allocation-TV dot-and-whisker plot.
- Directly labels shared Top-10 decision-cell counts and bootstrap intervals; no route-pair legend or vertical error bars are used.
- Uses an audit-style pairwise-TV axis beginning at zero with an upper bound rounded from the largest CI, rather than forcing `[0,1]`.
- Corrected the fast cohort-table bootstrap count from the full default of 1000 to the actual run value of 200.
- Separated the stable input content identity from local path and modification-time audit fields.
- Added bootstrap mean, median, bias, and point-outside-percentile-CI diagnostics without changing the frozen percentile bootstrap method.
- Reduced manuscript LaTeX tables to paper-facing fields while retaining complete reconstructable CSV audit tables.
- Changed the appendix allocation-TV matrix to an informative data-adaptive scale and displays only the nonredundant upper triangle.
- Expanded the synthetic contract fixture to cover all five delay bins: `<=1 h`, `1--6 h`, `6--24 h`, `1--7 d`, and `7--30 d`.
- Updated the programming memo and README to match the corrected output contract.

## Automated tests

```text
pytest -q
10 passed
```

The added regression checks cover:

- location-independent input content identity;
- nonzero synthetic support in all five delay bins;
- use of the actual fast bootstrap count in manuscript cohort outputs.

Existing tests continue to cover route-independent cohort construction, credit conservation, allocation normalization, frozen configuration, cell-level time decay, aggregate-versus-journey TV separation, and deterministic bootstrap results across worker counts.

## Final synthetic fast run

```text
run_id=exp2-fast-20260726T154447+0000
run_tier=fast
paper_result=false
input_kind=synthetic_contract_fixture
retained_journeys=810
retained_users=378
eligible_decision_cells=320
uid_bootstrap_repetitions=200
engineering_status=PASS
scientific_status=PASS
paper_promotion_status=INELIGIBLE_FAST
```

All reporting locations agree on 200 bootstrap repetitions. The run generated three PDF/SVG/PNG figures, exact figure source data and metadata, complete CSV audit tables, reduced manuscript LaTeX tables, route/cohort/bootstrap/input audits, and a finalized run manifest.

## Bootstrap diagnostic warning

Two of the six pairwise allocation-TV point estimates fall outside their percentile bootstrap intervals in the synthetic fast fixture. This is explicitly recorded as a `WARNING`, not a run failure. The estimator and interval method were not changed. The diagnostic should be reassessed on the real full run before any paper interpretation.

## Real-data boundary

The uploaded package did not contain `inputs/pcb_dataset_final.tsv`. This does not prevent synthetic fast validation. A paper-eligible result still requires the protected input and a non-overridden full run:

```bash
python -m pip install -r requirements.txt
# restore inputs/pcb_dataset_final.tsv
python main.py full
```

Full mode requires `pyarrow` and remains subject to independent promotion through `promote.py`.

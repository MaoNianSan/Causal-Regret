# Result-inspection notebook

`exp1_result_check.ipynb` is a read-only inspection notebook for an existing
Exp1 output bundle. It is intentionally stored without executed outputs so that
historical fast/full results are not mistaken for a fresh rerun.

After a completed run, the notebook inspects:

```text
outputs/<mode>/checks/self_check_report.csv
outputs/<mode>/summaries/
outputs/<mode>/tables/
outputs/<mode>/figures/data/
outputs/<mode>/figures/png/
outputs/<mode>/figures/pdf/
```

The canonical result-rebuild commands are documented in the project README.

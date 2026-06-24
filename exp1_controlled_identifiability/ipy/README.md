# Result-inspection notebooks

No executed result notebook is shipped with this clean source package. This
prevents historical fast/full outputs from being mistaken for a new rerun.

After a completed run, inspect:

```text
outputs/<mode>/checks/self_check_report.csv
outputs/<mode>/summaries/
outputs/<mode>/tables/
outputs/<mode>/figures/data/
outputs/<mode>/figures/png/
outputs/<mode>/figures/pdf/
```

The canonical result-rebuild commands are documented in the project README.

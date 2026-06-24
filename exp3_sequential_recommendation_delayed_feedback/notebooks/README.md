# Exp3 notebook audits

`exp3_figure_release_audit.ipynb` is a release-level visual contract audit for the promoted full Exp3 outputs.

Run it from the project root:

```bash
jupyter nbconvert --to notebook --execute notebooks/exp3_figure_release_audit.ipynb --output exp3_figure_release_audit_executed.ipynb --output-dir outputs/full/checks/
```

The notebook reads only existing `outputs/full` artifacts. It does not read KuaiRand raw inputs, refit proxies, rebuild targets, rerun bootstrap analysis, or modify summary/table estimates.

# Causal Regret Minimization Under Delayed Feedback

This repository is the GitHub-facing experiment package for **Causal Regret Minimization Under Delayed Feedback**. It is organized for paper-result inspection, lightweight smoke validation, and full reproduction by users who separately obtain the required external datasets.

No full experiment is run as part of this packaging layer. The committed notebooks and lightweight outputs are intended to make the current saved results viewable directly on GitHub.

## Experiment Index

| Directory | Question answered | Result notebook | Entrypoints |
| --- | --- | --- | --- |
| `exp1_controlled_identifiability` | When is delayed-feedback causal attribution identifiable in controlled simulations? | `exp1_controlled_identifiability/ipy/exp1_result_check.ipynb` | `reproduce_fast.py`, `reproduce_full.py`, `reproduce_paper.py`, `code_check.py`, `self_check.py` |
| `exp2_real_delayed_conversion_logs` | How do attribution routes behave on real delayed conversion logs? | `exp2_real_delayed_conversion_logs/ipy/exp2_result_check.ipynb` | `reproduce_fast.py`, `reproduce_full.py`, `reproduce_paper.py`, `code_check.py`, `self_check.py` |
| `exp3_sequential_recommendation_delayed_feedback` | How does delayed feedback affect sequential recommendation and proxy recovery? | `exp3_sequential_recommendation_delayed_feedback/ipy/exp3_result_check.ipynb` | `reproduce_fast.py`, `reproduce_full.py`, `code_check.py`, `self_check.py` |
| `exp4_proxy_sufficiency_impossibility` | When are proxy variables sufficient, and where do impossibility diagnostics appear? | `exp4_proxy_sufficiency_impossibility/ipy/exp4_result_check.ipynb` | `reproduce_all.py`, `run_experiment4.py`, `code_check.py`, `self_check.py` |
| `toy` | What is the minimal delayed-feedback recovery demonstration? | `toy/ipy/toy_result_check.ipynb` | `reproduce_fast.py`, `reproduce_full.py`, `reproduce_paper.py`, `code_check.py`, `self_check.py` |

The root overview notebook is `ipy/github_overview.ipynb`.

## Environment

Use Python 3.10 or newer. Install the root dependency set for package-wide checks:

```bash
pip install -r requirements.txt
```

Project-level `requirements.txt` files are also included where a narrower environment is useful.

## Data Dependencies

Exp1, Exp4, and `toy` are simulation-oriented and include lightweight saved outputs for inspection. Exp2 and Exp3 depend on external datasets that are intentionally **not** committed:

| Project | External data | Local placement |
| --- | --- | --- |
| `exp2_real_delayed_conversion_logs` | Criteo attribution / delayed conversion logs, subject to the source license. | `exp2_real_delayed_conversion_logs/inputs/` |
| `exp3_sequential_recommendation_delayed_feedback` | KuaiRand-1K source files, subject to the source license. | `exp3_sequential_recommendation_delayed_feedback/inputs/` |

The `inputs/README*.md` files document expected filenames and placement. Raw data, downloaded archives, and large processed files remain local and are excluded by `.gitignore`.

## Fast Checks And Full Reproduction

Fast checks are smoke tests only:

```bash
python exp1_controlled_identifiability/reproduce_fast.py
python exp2_real_delayed_conversion_logs/reproduce_fast.py
python exp3_sequential_recommendation_delayed_feedback/reproduce_fast.py
python toy/reproduce_fast.py
```

Full reproduction scripts, where present, are intended for complete reruns after external data is available:

```bash
python exp1_controlled_identifiability/reproduce_full.py
python exp2_real_delayed_conversion_logs/reproduce_full.py
python exp3_sequential_recommendation_delayed_feedback/reproduce_full.py
python toy/reproduce_full.py
```

Paper-facing scripts, where present, rebuild paper-interface artifacts from available outputs:

```bash
python exp1_controlled_identifiability/reproduce_paper.py
python exp2_real_delayed_conversion_logs/reproduce_paper.py
python toy/reproduce_paper.py
```

Do not expect Exp2 or Exp3 to complete a full reproduction without first obtaining and placing the required external datasets.

## Included Outputs

The package keeps lightweight GitHub-facing artifacts: notebooks, README files, documentation, run logs, figures, tables, summary CSV files, checks, metadata, reports, and output manifests. Large raw datasets, downloaded archives, processed parquet files, processed CSV intermediates, model/cache files, virtual environments, and runtime state are excluded.

## Notebook Viewing

Open these notebooks on GitHub to inspect saved outputs without rerunning experiments:

```text
ipy/github_overview.ipynb
exp1_controlled_identifiability/ipy/exp1_result_check.ipynb
exp2_real_delayed_conversion_logs/ipy/exp2_result_check.ipynb
exp3_sequential_recommendation_delayed_feedback/ipy/exp3_result_check.ipynb
exp4_proxy_sufficiency_impossibility/ipy/exp4_result_check.ipynb
toy/ipy/toy_result_check.ipynb
```

The notebooks use relative paths and are designed to read existing lightweight outputs. Missing nonessential artifacts should be reported as warnings rather than triggering full recomputation.

## File Size Policy

Files intended for upload should remain below 50 MB. The final audit files record the current size check and dry-run upload policy:

```text
FINAL_REPAIR_NOTES.md
FINAL_GITHUB_STRUCTURE.md
FINAL_GITIGNORE_POLICY.md
FINAL_NOTEBOOK_STATUS.csv
FINAL_FILE_SIZE_AUDIT.csv
FINAL_GITHUB_SYNC_PLAN.md
PREUPLOAD_CHECKLIST.md
```

## Citation

BibTeX entry pending final paper metadata:

```bibtex
@misc{causal_regret_delayed_feedback,
  title = {Causal Regret Minimization Under Delayed Feedback},
  author = {TBD},
  year = {2026},
  note = {Experiment package}
}
```

## License

Repository license selection is pending. See `LICENSE_PENDING.md` before public release. External datasets retain their original licenses and are not redistributed here.

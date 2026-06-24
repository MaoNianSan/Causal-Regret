# Causal Regret Minimization Under Delayed Feedback

This repository is the GitHub-facing experiment package for **Causal Regret
Minimization Under Delayed Feedback**. It is organized as a reproducibility
companion: readers can inspect saved paper-facing artifacts, run lightweight
checks, and rerun the experiments after obtaining external datasets that cannot
be redistributed here.

Committed notebooks, figures, tables, summaries, checks, metadata, and reports
are included for inspection. Full experiment reruns are intentionally separate
from packaging and require the documented local data placement.

## Repository Layout

| Directory | Role | Result notebook | Main entrypoints |
| --- | --- | --- | --- |
| `toy` | Minimal synthetic delayed-feedback diagnostic. | `toy/ipy/toy_result_check.ipynb` | `reproduce_fast.py`, `reproduce_full.py`, `reproduce_paper.py`, `code_check.py`, `self_check.py` |
| `exp1_controlled_identifiability` | Controlled simulation of source-binding identifiability under delayed feedback. | `exp1_controlled_identifiability/ipy/exp1_result_check.ipynb` | `reproduce_fast.py`, `reproduce_full.py`, `reproduce_paper.py`, `code_check.py`, `self_check.py` |
| `exp2_real_delayed_conversion_logs` | Logged attribution-sensitivity diagnostic on delayed conversion logs. | `exp2_real_delayed_conversion_logs/ipy/exp2_result_check.ipynb` | `reproduce_fast.py`, `reproduce_full.py`, `reproduce_paper.py`, `code_check.py`, `self_check.py` |
| `exp3_sequential_recommendation_delayed_feedback` | Offline recoverability diagnostic for constructed delayed engagement targets. | `exp3_sequential_recommendation_delayed_feedback/ipy/exp3_result_check.ipynb` | `reproduce_fast.py`, `reproduce_full.py`, `code_check.py`, `self_check.py` |
| `exp4_proxy_sufficiency_impossibility` | Synthetic stress test for source-label sufficiency and proxy-only limits. | `exp4_proxy_sufficiency_impossibility/ipy/exp4_result_check.ipynb` | `reproduce_all.py`, `run_experiment4.py`, `code_check.py`, `self_check.py` |
| `ipy` | Root overview notebook. | `ipy/github_overview.ipynb` | inspection only |

Each experiment directory has its own `README.md` with scope, data, run, and
output-contract details.

## Environment

Use Python 3.10 or newer. Install the root dependencies for repository-wide
inspection and checks:

```bash
python -m pip install -r requirements.txt
```

Some experiment directories also include a local `requirements.txt` when a
narrower environment is useful.

Development tools are listed separately:

```bash
python -m pip install -r requirements-dev.txt
```

## Code Formatting

Python formatting is standardized with Black. The root `pyproject.toml` defines
the formatting policy and excludes local data and generated output trees.

```bash
python -m black --check .
python -m black .
```

See `DEVELOPMENT.md` for code and documentation conventions.

## Data Dependencies

Exp1, Exp4, and `toy` are simulation-oriented. Exp2 and Exp3 require external
datasets that are intentionally not redistributed in this repository.

| Project | External data | Local placement |
| --- | --- | --- |
| `exp2_real_delayed_conversion_logs` | Criteo attribution / delayed conversion logs, subject to the source license. | `exp2_real_delayed_conversion_logs/inputs/` |
| `exp3_sequential_recommendation_delayed_feedback` | KuaiRand-1K source files, subject to the source license. | `exp3_sequential_recommendation_delayed_feedback/inputs/` |

The `inputs/README*.md` files document expected filenames and placement. Raw
data, downloaded archives, large processed intermediates, model/cache files,
virtual environments, and runtime state remain local and are excluded by
`.gitignore`.

## Fast Checks

Fast checks are smoke or interface checks. They are useful for confirming that
code paths and output contracts still work, but they are not paper-eligible full
runs.

```bash
python toy/reproduce_fast.py
python exp1_controlled_identifiability/reproduce_fast.py
python exp2_real_delayed_conversion_logs/reproduce_fast.py
python exp3_sequential_recommendation_delayed_feedback/reproduce_fast.py
python exp4_proxy_sufficiency_impossibility/reproduce_all.py --mode fast
```

Run the corresponding `self_check.py` after experiment reruns when the script
does not already invoke it.

## Full Reproduction

Full reproduction scripts are intended for complete reruns after required
external data is available:

```bash
python toy/reproduce_full.py
python exp1_controlled_identifiability/reproduce_full.py
python exp2_real_delayed_conversion_logs/reproduce_full.py
python exp3_sequential_recommendation_delayed_feedback/reproduce_full.py
python exp4_proxy_sufficiency_impossibility/reproduce_all.py --mode full
```

Paper-facing rebuild scripts, where present, refresh manuscript-interface
artifacts from available outputs:

```bash
python toy/reproduce_paper.py
python exp1_controlled_identifiability/reproduce_paper.py
python exp2_real_delayed_conversion_logs/reproduce_paper.py
```

Exp2 and Exp3 full reproduction will fail until the required external datasets
are placed in the documented local paths.

## Included Outputs

The repository keeps lightweight GitHub-facing artifacts for inspection and
reproducibility auditing:

- notebooks and README files;
- figures, figure source-data CSV files, and figure metadata;
- tables, summaries, checks, manifests, and reports;
- selected run logs and environment snapshots.

Protected raw data and large regenerated intermediates are excluded.

## Notebook Viewing

Open these notebooks on GitHub or locally to inspect saved outputs without
rerunning experiments:

```text
ipy/github_overview.ipynb
toy/ipy/toy_result_check.ipynb
exp1_controlled_identifiability/ipy/exp1_result_check.ipynb
exp2_real_delayed_conversion_logs/ipy/exp2_result_check.ipynb
exp3_sequential_recommendation_delayed_feedback/ipy/exp3_result_check.ipynb
exp4_proxy_sufficiency_impossibility/ipy/exp4_result_check.ipynb
```

The notebooks use relative paths and should treat missing nonessential artifacts
as warnings rather than as requests for full recomputation.

## File Size Policy

Files intended for GitHub should stay below 50 MB. Keep protected datasets,
downloaded archives, large processed intermediates, caches, and local runtime
state out of version control. The root `.gitignore` keeps lightweight outputs
visible while excluding common heavy artifacts.

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

Repository license selection is pending. External datasets retain their original
licenses and are not redistributed here.

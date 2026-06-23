# Validation record for this clean source package

## Completed before packaging

- All Python modules compiled successfully.
- `python code_check.py` completed successfully after the final implementation
  changes. Its isolated smoke run executed the entire 264-combination design and
  passed `self_check.py`.
- Targeted `T=5000` execution checks were run after the final implementation
  changes:
  - Gaussian-integrated EM on `state_structural_matched_15` emitted
    `em_delay_likelihood=gaussian_observable_state_integrated_quadrature` and
    conserved one feedback unit per observed arrival.
  - The stationary ablation emitted
    `em_delay_likelihood=stationary_geometric_ablation`.
  - Labelled ProxyAgent emitted `labelled_feature_alignment_max=0.0`.
  - On the same seed/path, the proxy quality contrast yielded a lower
    time-averaged state error for `proxy_good_matched_15` than for
    `proxy_bad_matched_15`; the low-quality condition also incurred higher
    causal regret in that targeted path.

## Not packaged as results

A full 792-run `fast` execution was started only to confirm the production
scheduler enters real tasks. It was stopped before completion and all partial
outputs were deleted. This package contains source, documentation, and an empty
`outputs/` directory only.

Run formal fast outputs locally or on the cloud with:

```powershell
python reproduce_fast.py
python self_check.py --mode fast
```

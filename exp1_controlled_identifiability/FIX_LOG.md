# EXP1 implementation log

## Current package status

This package is a clean source package. `outputs/` contains no historical fast,
smoke, or partial run products.

## Fixed in this package

1. **Proxy feature-space mismatch**
   - `ProxyAgent._labelled_source_feature()` now reads the source-time saved
     Kalman feature from `history[src_t]['x']`.
   - It never reads `item['src_x']`.
   - `labelled_feature_alignment_max` is exported and audited.

2. **Structural EM plug-in prior**
   - Default structural EM now uses Gaussian observable-state integration with
     Gauss--Hermite quadrature.
   - The state simulation is untruncated Gaussian AR(1), matching the analytic
     state posterior used by the comparator and EM.
   - The prior implementation is recorded in `em_delay_likelihood`.

3. **Method interpretation**
   - `causal_em` is displayed as Gaussian-integrated EM.
   - `causal_em_misspecified` is displayed as Stationary-geometric EM.
   - Neither is described as a universally correctly specified or impossible
     recovery procedure.

4. **Proxy-quality control**
   - Good and bad settings share state/context/delay paths and learner random
     tape; only extra proxy observation noise differs.
   - Noise levels are 0.20 and 4.00, respectively.

5. **Runtime guards**
   - `code_check.py` compiles the project, validates the two new source-level
     contracts, and runs a full 264-combination smoke design.
   - `self_check.py` validates EM likelihood labels, proxy alignment, and the
     proxy-error quality contrast in addition to the previous output contract.

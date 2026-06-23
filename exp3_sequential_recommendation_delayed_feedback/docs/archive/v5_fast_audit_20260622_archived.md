# Audit of the preceding real-data fast output

This note preserves the interpretation of the real-data fast output supplied
with the preceding Exp3 package. Those values are archived as an engineering
audit only and must not be copied into the v5 result contract or paper figures.

## What the preceding output established

The preceding run used real KuaiRand-1K standard-feed logs, a 6h constructed
target, a history-defined action vocabulary, a temporally valid carrier rule,
and a finite partial-label mask bank. It therefore established that the full
pipeline can execute with real input and produce the intended figure bundles.

## Why it is not v5-compatible

1. **Proxy fallback look-ahead.** The earlier proxy implementation used a
   global proxy/composite mean computed from the full main split whenever an
   action lacked a prior-bin observation. That mean included future main bins.
   V5 replaces it with a completed-history plus earlier-main expanding fallback.
2. **Training-feature look-ahead.** The analogous history training fallback was
   computed from the complete history split. V5 uses only earlier history bins
   for every historical training row.
3. **Promotion contract gap.** The earlier promotion gate updated only the run
   manifest. V5 regenerates figure CSV/JSON/PDF/PNG bundles and the artifact
   manifest when a real full run is promoted.
4. **Mask uncertainty wording.** The earlier implementation sampled from a
   finite bank of mask trajectories but described this as fresh regeneration per
   bootstrap draw. V5 uses the accurate finite-mask-bank wording.

## Consequence

The old real-data fast output may be retained as evidence that code paths and
input schemas were operational. It cannot predict v5 full point estimates,
intervals, calibration, or figure values. Run v5 fast on the real input before
starting v5 full.

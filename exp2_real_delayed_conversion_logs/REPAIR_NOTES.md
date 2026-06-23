# Repair notes

## Earlier integrity repairs retained

1. UID bootstrap now excludes invalid journeys before sparse-matrix construction:
   - missing UID;
   - missing or sentinel `conversion_id`;
   - a `conversion_id` appearing under multiple UIDs.
2. Every candidate-window analysis builds/uses a window-compatible UID reference and reports its own audit row.
3. Old temporal replay, label-availability, and single-permutation controls are absent from the formal pipeline.

## This semantic/figure repair

1. Renamed primary fields from utility-like names to credit-summary names:
   - `top_k_credited_mass_per_1000_events`;
   - `credit_allocation_tv_distance_vs_arrival_anchor`;
   - `top_k_decision_cell_overlap_vs_arrival_anchor`.
2. Main figure Panel B now maps allocation TV distance against ranking overlap; it does not map credited-mass displacement.
3. Main figure excludes `soft_attribution_em`; EM remains in computation, non-degeneracy gates, and a table audit.
4. Display names now state `First click or touch` and `Last click or touch` because both routes explicitly fall back to source touches when clicks are unavailable.
5. Unique-labelled source-linked, candidate-window, and EM diagnostics are tables rather than low-information figures.
6. Replaced the old top-k line plot with a pairwise source-route TV and top-10 overlap heatmap appendix figure.
7. Route-degeneracy gate now evaluates core source-route pairs, not merely any pair involving the arrival anchor.

## Required rerun scope

This repair changes statistics output fields, bootstrap summaries, tables, figure data, figure metadata, and self-check contracts. Run a clean fast pipeline from `main.py`; do not reuse any prior output directory.

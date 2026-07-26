# Exp4 migration record

- Legacy directory: `exp4_proxy_sufficiency_impossibility`
- Current directory: `exp4_controlled_route_audit`
- Legacy result schema: `legacy_exp4_v1`
- Current result schema: `exp4_controlled_route_audit_v1`
- Legacy outputs are retained only through repository history or a legacy tag.
- Legacy outputs cannot reconstruct deterministic structural loss maps, full route maps, independent route/audit masks, extended observation clocks, or cross-fitted audit targets.
- Reuse status: `REQUIRES_RERUN`.

The active runner rejects the legacy schema and never reads legacy summaries or figures.

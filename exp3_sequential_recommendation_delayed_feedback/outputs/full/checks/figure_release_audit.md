# Figure release audit

- Status: passed
- Run: `full_20260624T081725Z_ff80ce71f7`
- ST ridge versus History mean paired estimate: 0.0043 [-0.0050, 0.0147]

## Manual checklist

- [ ] no clipped tick labels
- [ ] no legend overlaps
- [ ] Carrier baseline visible
- [ ] Reference marked offline
- [ ] all CI explanations visible
- [ ] horizon figure does not use the word saturation

## Machine checks

- `manifest_contract`: passed - {"run_id": "full_20260624T081725Z_ff80ce71f7", "run_mode": "full", "input_data_status": "real_kuairand_1k", "paper_result": true, "status": "complete"}
- `main_panel_b_methods`: passed - source_aware_reference,partial_source_label_q50,partial_source_label_q30,partial_source_label_q10,history_mean_static,short_term_ridge_proxy,short_term_composite_surrogate
- `main_panel_a_proxy`: passed - short_term_ridge_proxy only
- `visual_contract_metadata`: passed - main and horizon visual_contract fields match
- `paired_static_control`: passed - ST ridge versus History mean paired estimate: 0.0043 [-0.0050, 0.0147]
- `manual_visual_checklist`: passed - no clipped tick labels; no legend overlaps; Carrier baseline visible; Reference marked offline; all CI explanations visible; horizon figure does not use the word saturation

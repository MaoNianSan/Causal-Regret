# Exp1 V2 Presentation Patch - Baseline Audit

- Repo root: `D:\research\causalregret\experiment\github`
- Branch: `main`
- HEAD commit: `f75064d9abf1f499e6aa84a794f8971dd407e93f`
- Calibration manifest hash: `b4bf2ad829be75d27f6ac4d3792968e90467c80f1b4949e56d7f1566f488630b`
- Calibration code lineage: `tree:7821dc5d1f9cb634b1ce180ce8310b2d357ee89184a76b06e08bee5097093fe2`
- Full run id: `exp1_alignment_transfer:full:2026-07-26T11:53:17.328965+00:00`
- Full config hash: `21563d9a7d6a3134d56776beef7f02b88fbe31e8f18ac118a957eac374c3df02`
- Current main figure PNG sha256: `03b94bfdda96ac02cf158ad19074d6cfb0074204c4d2335609db5eb0d5366778`

## Frozen scientific artifacts (must remain byte-identical)

| Path | sha256 |
|---|---|
| `outputs/full/seed_metrics/exp1_route_seed_metrics.csv` | `ee710d1af2cc5af4e3f1f9df0f0fa95038ca988c13d8120293762ddbf09d3dd1` |
| `outputs/full/seed_metrics/exp1_route_seed_metrics.parquet` | `6f82aba54054791632e8b38db30fddbd53a4b86f9b34f4ceb45d7a4e8997c0ae` |
| `outputs/full/seed_metrics/exp1_learner_seed_metrics.csv` | `c89457f9a09cb2cbb5804f92cdda5747159a628d0ce893ccfa37dc711b8f7af5` |
| `outputs/full/seed_metrics/exp1_learner_seed_metrics.parquet` | `20c3585c903cfcc3a39ad840e11a854e4fdd36269440bf9a30a16be80f3f88f1` |
| `outputs/full/derived/exp1_route_summary.csv` | `64d7e9bb16df75ae83aee6eabceb647c48c1ae60cc57ef00c44bd114a331c925` |
| `outputs/full/derived/exp1_learner_summary.csv` | `1cc19a88349e837c251222a9eb9fb92842ba3dbe0ed2319c3253d55139fc05da` |
| `outputs/full/derived/exp1_primary_summary.csv` | `aab243f741859b2e8223d57d896336a6da64ab783bfe48e23a92c3156a453eb6` |
| `outputs/full/derived/exp1_actual_learner_contrasts.csv` | `c242a34e90b215a2b2ade8cbbbd3ef8f750c474e2aa2d4159f131cfac5ff9fec` |
| `outputs/full/checks/exp1_validation_report.json` | `11e3da0eb28a8016deb902a4ab693928ec7386504392c31dd8145c3fba538bd8` |
| `outputs/full/targeted/exp1_targeted_horizon_seed_metrics.csv` | `1cd85515f2eb43f3a0044c68bd8c859f1bace4c12f3b6389e0622b12b0c21145` |
| `outputs/full/targeted/exp1_targeted_horizon_summary.csv` | `38cd52329cfb5d672e5ae4c9a894bea59d7a5a5c5e3b2437e3d844d1b18f48d1` |
| `outputs/full/targeted/exp1_targeted_mean_delay_seed_metrics.csv` | `b8f5ceff9f513fef1155ffef003a3e0809b95060f570777638fd45f9b795cc8e` |
| `outputs/full/targeted/exp1_targeted_mean_delay_summary.csv` | `8e9849e6a68cbff356c6ec5f5a7e688ee0bc4b24abe8b4ff7922e12a99bba6fa` |
| `outputs/full/targeted/exp1_targeted_validation_report.json` | `2d05a02643e5674779656c72acb0e4e9d416e09d49b65a5f90ea6af348eaecb1` |
| `outputs/full/manuscript/exp1_manuscript_values.json` | `9b1291939560eb7b03e055db0b64ad1827db0c5c7298f2e76818874e7557417d` |
| `outputs\full\figures\data\fig_exp1_alignment_transfer_data.csv` | `7dcd0a5be962dad9ef98ceb8f9eadbdc7f4e0d1b7909b59576f17bf9a971184a` |
| `outputs\full\figures\data\fig_exp1_delay_survival_data.csv` | `11022b4d6aa4067a2336e2af877448668b93d7917c712dc0082ddfd36355dca5` |
| `outputs\full\figures\data\fig_exp1_reversal_margin_data.csv` | `047253d4529f09d40dd8d2637bcbd553d598391eea80c396b34d7d60f436ab70` |
| `outputs\full\figures\data\fig_exp1_route_trajectory_data.csv` | `7607e32f82597b18e6970ece92e94cb95d06d6da631020d6df363e269a129a42` |
| `outputs\full\figures\data\fig_exp1_state_coupling_data.csv` | `0e1489d73aa4fcf9ff5aef284f085ca5cd22304065f6b16cce946dfecb49c2ae` |

## Full validation status (baseline)
```json
{
  "calibration_manifest_hash": "b4bf2ad829be75d27f6ac4d3792968e90467c80f1b4949e56d7f1566f488630b",
  "code_commit": "6e09fa90a1fcdeccc861cf2960bd31c4b60e2df4",
  "code_lineage": "tree:7821dc5d1f9cb634b1ce180ce8310b2d357ee89184a76b06e08bee5097093fe2",
  "engineering_status": "PASS",
  "generated_at": "2026-07-26T11:59:54.370271+00:00",
  "paper_promotion_status": "ELIGIBLE_FOR_PROMOTION_REVIEW",
  "paper_result": false,
  "report": "outputs/full/checks/exp1_validation_report.json",
  "scientific_status": "PASS",
  "stage": "full_validation",
  "status": "PASS"
}
```
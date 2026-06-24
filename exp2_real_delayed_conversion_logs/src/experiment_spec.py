from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FAST_BOOTSTRAP_REPLICATES = 200
FULL_BOOTSTRAP_REPLICATES = 1000


def resolve_experiment_spec(mode: str) -> dict:
    if mode not in {"fast", "full"}:
        raise ValueError(f"Unsupported mode: {mode}")
    n_bootstrap = (
        FAST_BOOTSTRAP_REPLICATES if mode == "fast" else FULL_BOOTSTRAP_REPLICATES
    )
    return {
        "project_id": "exp2_logged_attribution_sensitivity",
        "mode": mode,
        "uid_bootstrap_replicates": n_bootstrap,
        "input_requirement": "inputs/pcb_dataset_final.tsv",
        "output_root": f"outputs/{mode}",
    }

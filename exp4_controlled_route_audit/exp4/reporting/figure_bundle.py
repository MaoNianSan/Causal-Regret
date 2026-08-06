"""Figure bundle writer with frozen-source provenance."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from exp4.configuration.parameters import REPORTING
from exp4.configuration.schema import EXPERIMENT_ID, RESULT_SCHEMA
from exp4.outputs.writers import sha256_file, write_json


def save_figure_bundle(
    figure: plt.Figure,
    run_dir: Path,
    figure_id: str,
    figure_data: pd.DataFrame,
    source_files: list[Path],
    metadata: dict[str, Any],
) -> None:
    pdf_path = run_dir / "figures" / "pdf" / f"{figure_id}.pdf"
    png_path = run_dir / "figures" / "png" / f"{figure_id}.png"
    data_path = run_dir / "figures" / "data" / f"{figure_id}_data.csv"
    metadata_path = run_dir / "figures" / "metadata" / f"{figure_id}_metadata.json"
    figure.savefig(pdf_path)
    figure.savefig(png_path, dpi=REPORTING.paper_dpi)
    figure_data.to_csv(data_path, index=False)
    run_config = json.loads(
        (run_dir / "logs" / "run_config.json").read_text(encoding="utf-8")
    )
    calibration = json.loads(
        (
            run_dir
            / "derived"
            / "calibration"
            / "exp4_proxy_route_calibration.json"
        ).read_text(encoding="utf-8")
    )
    write_json(
        {
            "figure_id": figure_id,
            "experiment_id": EXPERIMENT_ID,
            "result_schema": RESULT_SCHEMA,
            "source_derived_files": [
                path.relative_to(run_dir).as_posix() for path in source_files
            ],
            "source_file_hashes": {
                path.relative_to(run_dir).as_posix(): sha256_file(path)
                for path in source_files
            },
            "code_commit": run_config["code_commit"],
            "config_hash": run_config["config_hash"],
            "calibration_hash": calibration["calibration_hash"],
            "run_tier": run_config["run_tier"],
            "paper_result": bool(run_config["paper_result"]),
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            **metadata,
        },
        metadata_path,
    )
    plt.close(figure)

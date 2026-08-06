from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from data_io import write_json

from .artifact_metadata import save_figure, sha256
from .source_data import PAIR_LABELS, build_ambiguity_figure_source
from .style import set_publication_style


def make_ambiguity_figure(
    ambiguity: pd.DataFrame,
    output_dir: str | Path,
    config: dict[str, Any],
    *,
    run_metadata: dict[str, Any],
) -> dict[str, Any]:
    set_publication_style(config)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    source = build_ambiguity_figure_source(ambiguity, run_id=run_metadata["run_id"])
    source_path = output_dir / "figure_exp2_ambiguity_mechanism_source.csv"
    source.to_csv(source_path, index=False)

    strata = ["candidate_cells_1", "candidate_cells_2", "candidate_cells_3plus"]
    pair_order = [PAIR_LABELS[pair] for pair in PAIR_LABELS]
    matrix = source.pivot_table(
        index="display_label",
        columns="candidate_cell_count_stratum",
        values="mean_journey_assignment_tv",
        aggfunc="first",
    ).reindex(index=pair_order, columns=strata)
    fig, ax = plt.subplots(figsize=(5.6, 3.4), constrained_layout=True)
    image = ax.imshow(matrix.to_numpy(dtype=float), vmin=0.0, vmax=1.0, cmap="viridis")
    ax.set_xticks(range(len(strata)), ["1 cell", "2 cells", "3+ cells"])
    ax.set_yticks(range(len(pair_order)), pair_order)
    for row_index in range(len(pair_order)):
        for column_index in range(len(strata)):
            value = matrix.iloc[row_index, column_index]
            ax.text(column_index, row_index, "NA" if pd.isna(value) else f"{value:.2f}", ha="center", va="center", fontsize=7)
    ax.set_xlabel("Candidate source cells per journey")
    ax.set_title("Mean journey assignment TV")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    base = output_dir / "figure_exp2_ambiguity_mechanism"
    files = save_figure(fig, base, config)
    plt.close(fig)
    metadata = {
        **run_metadata,
        "figure_id": "figure_exp2_ambiguity_mechanism",
        "source_data": source_path.name,
        "source_data_sha256": sha256(source_path),
        "figure_files": {path.name: sha256(path) for path in files},
    }
    metadata_path = output_dir / "figure_exp2_ambiguity_mechanism_metadata.json"
    write_json(metadata, metadata_path)
    return {"figure_files": files, "source_data": source_path, "metadata": metadata_path}

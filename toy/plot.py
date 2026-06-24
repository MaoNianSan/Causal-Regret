import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from io_utils import ensure_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot Toy appendix trajectories.")
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Toy outputs directory relative to plot.py or absolute path.",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "fast"],
        default="full",
        help="Use outputs/full or outputs/fast mode directories.",
    )
    return parser.parse_args()


def resolve_output_dir(base: Path, output_dir: str, mode: str) -> Path:
    path = Path(output_dir)
    if path.is_absolute():
        return path / mode
    return (base / output_dir / mode).resolve()


def ci95_bounds(mean: np.ndarray, se: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    margin = 1.96 * se
    return mean - margin, mean + margin


def plot_trajectories(
    df: pd.DataFrame,
    out_pdf: Path,
    out_png: Path,
    label_map: dict[str, str],
) -> None:
    delay_settings = sorted(df["delay_setting"].unique())
    cols = 2
    rows = int(np.ceil(len(delay_settings) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(13.0, 4.5 * rows), squeeze=False)

    for idx, delay_setting in enumerate(delay_settings):
        row = idx // cols
        col = idx % cols
        ax = axes[row][col]
        subset = df[df["delay_setting"] == delay_setting]
        x = np.array(sorted(subset["t"].unique()))

        for method_index, (method, color, marker) in enumerate(
            [
                ("oracle", "C2", "s"),
                ("naive", "C0", "o"),
                ("causal_labelled", "C1", "^"),
            ]
        ):
            method_df = subset[subset["method"] == method]
            if method_df.empty:
                continue
            mean = method_df["mean_cumulative_Rc"].to_numpy(dtype=float)
            se = method_df["se_cumulative_Rc"].to_numpy(dtype=float)
            lower, upper = ci95_bounds(mean, se)
            ax.plot(
                x,
                mean,
                label=label_map[method],
                color=color,
                marker=marker,
                markevery=(method_index * 17, 90),
                markersize=3.5,
                linewidth=1.5,
                zorder=3 + method_index,
            )
            ax.fill_between(x, lower, upper, alpha=0.2, color=color)

        ax.set_title(delay_setting)
        ax.set_xlabel("Structural time t")
        ax.set_ylabel("Cumulative structural causal regret R_t^c")
        ax.grid(True, linestyle="--", alpha=0.4)
        if idx == 0:
            ax.legend()

    for idx in range(len(delay_settings), rows * cols):
        fig.delaxes(axes[idx // cols][idx % cols])

    fig.tight_layout()
    ensure_dir(out_pdf.parent)
    fig.savefig(out_pdf, format="pdf")
    fig.savefig(out_png, format="png", dpi=300)
    plt.close(fig)


def generate_figures(output_root: Path) -> None:
    summary_dir = output_root / "summary"
    figures_dir = output_root / "figures"
    ensure_dir(figures_dir)

    trajectory_path = summary_dir / "toy_trajectory_summary.csv"
    if not trajectory_path.exists():
        raise FileNotFoundError(f"Missing trajectory summary: {trajectory_path}")

    df = pd.read_csv(trajectory_path)
    df["t"] = df["t"].astype(int)
    df["mean_cumulative_Rc"] = df["mean_cumulative_Rc"].astype(float)
    df["se_cumulative_Rc"] = df["se_cumulative_Rc"].astype(float)

    label_map = {
        "oracle": "Oracle",
        "naive": "Naive",
        "causal_labelled": "Causal-labelled",
    }
    selected_settings = ["0_delay", "geom_0.15", "piece_0.6to0.15"]

    df_selected = df[df["delay_setting"].isin(selected_settings)].copy()
    df_selected.to_csv(figures_dir / "toy_selected_trajectories_data.csv", index=False)
    df.to_csv(figures_dir / "toy_full_trajectories_data.csv", index=False)

    plot_trajectories(
        df_selected,
        figures_dir / "toy_selected_trajectories.pdf",
        figures_dir / "toy_selected_trajectories.png",
        label_map,
    )
    plot_trajectories(
        df,
        figures_dir / "toy_full_trajectories.pdf",
        figures_dir / "toy_full_trajectories.png",
        label_map,
    )


def main() -> None:
    args = parse_args()
    base = Path(__file__).resolve().parent
    output_root = resolve_output_dir(base, args.output_dir, args.mode)
    generate_figures(output_root)


if __name__ == "__main__":
    main()

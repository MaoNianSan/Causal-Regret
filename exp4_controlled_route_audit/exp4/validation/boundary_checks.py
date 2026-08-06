"""Checks that Exp4 artifacts do not absorb Exp1 learner/regret evidence."""

from __future__ import annotations

from pathlib import Path


BANNED_PRIMARY_TERMS = (
    "structural_regret",
    "route_regret",
    "learner",
    "regret_transfer",
    "delay_mechanism",
    "proxy_impossibility",
    "validity_probability",
)


def exp1_exp4_boundary_check(run_dir: Path, main_figure_id: str, main_table_id: str) -> tuple[bool, str]:
    paths = (
        run_dir / "figures" / "data" / f"{main_figure_id}_data.csv",
        run_dir / "figures" / "metadata" / f"{main_figure_id}_metadata.json",
        run_dir / "tables" / f"{main_table_id}.csv",
        run_dir / "tables" / f"{main_table_id}.tex",
    )
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)
    present = [term for term in BANNED_PRIMARY_TERMS if term in text]
    return not present, f"banned_terms_present={present}"

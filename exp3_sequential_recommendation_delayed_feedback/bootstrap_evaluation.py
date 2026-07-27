"""User-cluster resampling with complete support/gap/ranking reconstruction."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from audit_design import AuditDesign
from bootstrap_summary import summarize_bootstrap
from config import DEFAULT_CONFIG, ExperimentConfig
from dependence_diagnostics import compare_replication_structure
from evaluate_recoverability import _assign_deciles, compute_metrics
from evaluation_artifacts import EvaluationArrays, MetricResult
from utilities import read_frame, save_frame


def _bootstrap_weights(user_count: int, seed: int, replication_id: int) -> np.ndarray:
    """Generate one schedule-independent user-cluster resampling draw."""
    seed_sequence = np.random.SeedSequence([int(seed), int(replication_id)])
    rng = np.random.default_rng(seed_sequence)
    return rng.multinomial(user_count, np.full(user_count, 1.0 / user_count)).astype(float)


def _run_replication(
    replication_id: int,
    arrays: EvaluationArrays,
    design: AuditDesign,
    point_result: MetricResult,
    decile_membership: dict[tuple[str, str, int, str], int],
    cfg: ExperimentConfig,
) -> tuple[
    int,
    pd.DataFrame | None,
    pd.DataFrame | None,
    pd.DataFrame | None,
    pd.DataFrame | None,
    str | None,
]:
    try:
        weights = _bootstrap_weights(len(arrays.user_ids), cfg.bootstrap_seed, replication_id)
        result = compute_metrics(
            arrays,
            design,
            user_weights=weights,
            decile_membership=decile_membership,
            cfg=cfg,
        )
        routes = result.route_metrics.copy()
        routes["replication_id"] = replication_id
        deciles = result.decile_calibration.copy()
        deciles["replication_id"] = replication_id
        support = result.support_metrics.copy()
        support["replication_id"] = replication_id
        structure = compare_replication_structure(point_result, result, replication_id)
        return replication_id, routes, deciles, support, structure, None
    except Exception as exc:  # replication-level failures are audited, not hidden
        return replication_id, None, None, None, None, f"{type(exc).__name__}: {exc}"


def _load_partial(path: Path) -> pd.DataFrame:
    try:
        return read_frame(path)
    except FileNotFoundError:
        return pd.DataFrame()


def _complete_valid_replications(*frames: pd.DataFrame) -> set[int]:
    if any(frame.empty for frame in frames):
        return set()
    ids = [set(frame["replication_id"].astype(int).unique()) for frame in frames]
    return set.intersection(*ids)


def _write_checkpoint(
    checkpoint_path: Path,
    repetitions: int,
    completed_ids: set[int],
    valid_ids: set[int],
    invalid_ids: set[int],
    n_jobs: int,
) -> None:
    pd.DataFrame(
        [
            {
                "requested_repetitions": repetitions,
                "last_completed_replication": max(completed_ids) if completed_ids else -1,
                "completed_repetitions": len(completed_ids),
                "valid_repetitions": len(valid_ids),
                "invalid_repetitions": len(invalid_ids),
                "n_jobs": max(1, int(n_jobs)),
                "replication_seed_rule": "SeedSequence([bootstrap_seed, replication_id])",
            }
        ]
    ).to_csv(checkpoint_path, index=False)


def _persist_draws(
    route_draws: pd.DataFrame,
    decile_draws: pd.DataFrame,
    support_draws: pd.DataFrame,
    structure_draws: pd.DataFrame,
    invalid: pd.DataFrame,
    output_dir: Path,
) -> None:
    save_frame(route_draws, output_dir / "derived" / "exp3_bootstrap_route_draws.parquet")
    save_frame(decile_draws, output_dir / "derived" / "exp3_bootstrap_decile_draws.parquet")
    save_frame(support_draws, output_dir / "derived" / "exp3_bootstrap_support_draws.parquet")
    save_frame(structure_draws, output_dir / "derived" / "exp3_bootstrap_structure_draws.parquet")
    invalid.sort_values("replication_id").to_csv(
        output_dir / "checks" / "exp3_bootstrap_invalid_replications.csv", index=False
    )


def run_user_cluster_bootstrap(
    arrays: EvaluationArrays,
    design: AuditDesign,
    point_result: MetricResult,
    output_dir: Path,
    run_tier: str,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
    *,
    n_jobs: int = 1,
    resume: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    repetitions = cfg.bootstrap_repetitions(run_tier)
    n_jobs = max(1, int(n_jobs))
    decile_membership = _assign_deciles(point_result.action_cell_metrics)
    checkpoint_path = output_dir / "checks" / "exp3_bootstrap_checkpoint.csv"
    route_path = output_dir / "derived" / "exp3_bootstrap_route_draws.parquet"
    decile_path = output_dir / "derived" / "exp3_bootstrap_decile_draws.parquet"
    support_path = output_dir / "derived" / "exp3_bootstrap_support_draws.parquet"
    structure_path = output_dir / "derived" / "exp3_bootstrap_structure_draws.parquet"
    invalid_path = output_dir / "checks" / "exp3_bootstrap_invalid_replications.csv"

    if resume:
        route_draws = _load_partial(route_path)
        decile_draws = _load_partial(decile_path)
        support_draws = _load_partial(support_path)
        structure_draws = _load_partial(structure_path)
        invalid = (
            pd.read_csv(invalid_path)
            if invalid_path.exists()
            else pd.DataFrame(columns=["replication_id", "error"])
        )
    else:
        route_draws = pd.DataFrame()
        decile_draws = pd.DataFrame()
        support_draws = pd.DataFrame()
        structure_draws = pd.DataFrame()
        invalid = pd.DataFrame(columns=["replication_id", "error"])

    valid_ids = _complete_valid_replications(route_draws, decile_draws, support_draws, structure_draws)
    if valid_ids:
        for name, frame in (
            ("route", route_draws),
            ("decile", decile_draws),
            ("support", support_draws),
            ("structure", structure_draws),
        ):
            filtered = frame[frame["replication_id"].astype(int).isin(valid_ids)].copy()
            if name == "route":
                route_draws = filtered
            elif name == "decile":
                decile_draws = filtered
            elif name == "support":
                support_draws = filtered
            else:
                structure_draws = filtered
    invalid_ids = set(invalid["replication_id"].astype(int).tolist()) if not invalid.empty else set()
    remaining = [i for i in range(repetitions) if i not in (valid_ids | invalid_ids)]
    chunk_size = max(10, 5 * n_jobs)

    for start in range(0, len(remaining), chunk_size):
        batch_ids = remaining[start : start + chunk_size]
        if n_jobs > 1 and len(batch_ids) > 1:
            with ThreadPoolExecutor(max_workers=n_jobs) as executor:
                results = list(
                    executor.map(
                        lambda i: _run_replication(
                            i, arrays, design, point_result, decile_membership, cfg
                        ),
                        batch_ids,
                    )
                )
        else:
            results = [
                _run_replication(i, arrays, design, point_result, decile_membership, cfg)
                for i in batch_ids
            ]

        route_parts: list[pd.DataFrame] = []
        decile_parts: list[pd.DataFrame] = []
        support_parts: list[pd.DataFrame] = []
        structure_parts: list[pd.DataFrame] = []
        invalid_rows: list[dict[str, object]] = []
        for replication_id, routes, deciles, support, structure, error in results:
            if error is not None:
                invalid_rows.append({"replication_id": replication_id, "error": error})
                invalid_ids.add(replication_id)
                continue
            assert routes is not None and deciles is not None and support is not None and structure is not None
            route_parts.append(routes)
            decile_parts.append(deciles)
            support_parts.append(support)
            structure_parts.append(structure)
            valid_ids.add(replication_id)
        if route_parts:
            route_draws = pd.concat([route_draws, *route_parts], ignore_index=True)
            decile_draws = pd.concat([decile_draws, *decile_parts], ignore_index=True)
            support_draws = pd.concat([support_draws, *support_parts], ignore_index=True)
            structure_draws = pd.concat([structure_draws, *structure_parts], ignore_index=True)
        if invalid_rows:
            invalid = pd.concat([invalid, pd.DataFrame(invalid_rows)], ignore_index=True)
        _persist_draws(route_draws, decile_draws, support_draws, structure_draws, invalid, output_dir)
        _write_checkpoint(
            checkpoint_path,
            repetitions,
            valid_ids | invalid_ids,
            valid_ids,
            invalid_ids,
            n_jobs,
        )

    route_draws = route_draws.sort_values(["replication_id", "route_id"], kind="stable").reset_index(drop=True)
    decile_draws = decile_draws.sort_values(
        ["replication_id", "route_id", "calibration_decile"], kind="stable"
    ).reset_index(drop=True)
    support_draws = support_draws.sort_values("replication_id", kind="stable").reset_index(drop=True)
    structure_draws = structure_draws.sort_values(["replication_id", "route_id"], kind="stable").reset_index(drop=True)
    invalid = invalid.sort_values("replication_id", kind="stable").reset_index(drop=True)
    valid_count = len(valid_ids)
    valid_fraction = valid_count / repetitions if repetitions else 0.0
    if valid_fraction < cfg.valid_bootstrap_fraction_gate:
        raise RuntimeError(
            f"Only {valid_fraction:.3f} of user-resampling replicates were valid; "
            f"the gate is {cfg.valid_bootstrap_fraction_gate:.3f}."
        )

    invalid_records = invalid[["replication_id", "error"]].to_dict("records") if not invalid.empty else []
    summary, paired, decile_summary, diagnostics = summarize_bootstrap(
        route_draws=route_draws,
        decile_draws=decile_draws,
        support_draws=support_draws,
        structure_draws=structure_draws,
        point_result=point_result,
        output_dir=output_dir,
        repetitions=repetitions,
        valid_count=valid_count,
        invalid_count=len(invalid_ids),
        invalid_records=invalid_records,
        n_jobs=n_jobs,
        resumed=resume,
        cfg=cfg,
    )
    _persist_draws(route_draws, decile_draws, support_draws, structure_draws, invalid, output_dir)
    _write_checkpoint(
        checkpoint_path,
        repetitions,
        valid_ids | invalid_ids,
        valid_ids,
        invalid_ids,
        n_jobs,
    )
    return summary, paired, decile_summary, diagnostics

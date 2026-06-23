from __future__ import annotations

"""Standalone EXP1 execution backend.

The runner enforces the revised experiment contract:
1. all learners observe decision-time X_t;
2. causal regret is excess conditional risk against the X_t-information oracle;
3. primary delay paths are pre-generated and shared across methods;
4. action-dependent delay is isolated as a policy-dependent stress test;
5. feedback is updated per source outcome, never per arrival batch.
"""

import csv
import hashlib
import json
import os
import platform
import random
import shutil
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache, partial
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from config import D_MAX, FAST_SEEDS, FAST_T, K, SEEDS, T
from src.agents import (
    AnonymousDelayedAgent,
    CausalEMAgent,
    CausalLabeledAgent,
    DelayedEXP3Agent,
    DelayedUCBAgent,
    NaiveAgent,
    NaiveEWMAAgent,
    OracleAgent,
    ProxyAgent,
    SlidingWindowAgent,
)
from src.delay import CONTEXT_NOISE_SD, ScenarioTrace, build_scenario_trace, scenario_definitions
from src.environment import ToyDelayedEnv
from src.io_utils import compute_config_hash
from src.plot_utils import plot_exp1_bundles

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ID = "exp1_controlled_identifiability_contextual"
METHODS = (
    "oracle",
    "naive",
    "naive_ewma",
    "delayed_ucb",
    "delayed_exp3",
    "sliding_window_W250",
    "anonymous_delayed",
    "causal_labeled",
    "causal_em",
    "causal_em_misspecified",
    "proxy",
)
REGIMES = ("labelled", "mixture_labelled", "unlabelled")
SETTINGS = tuple(scenario_definitions().keys())
PRIMARY_MATCHED_SETTINGS = (
    "geometric_matched_15",
    "mixture_matched_15",
    "state_structural_matched_15",
)
Task = tuple[int, str, str, str]


@dataclass(frozen=True)
class RunOptions:
    mode: str
    raw_log_mode: str
    smoke: bool = False
    output_tag: str | None = None

    @property
    def seeds(self) -> list[int]:
        return [int(FAST_SEEDS[0])] if self.smoke else list(FAST_SEEDS if self.mode == "fast" else SEEDS)

    @property
    def horizon(self) -> int:
        return int(os.environ.get("EXP1_SMOKE_T", "80")) if self.smoke else int(FAST_T if self.mode == "fast" else T)

    @property
    def output_name(self) -> str:
        return str(self.output_tag or self.mode)

    @property
    def output_root(self) -> Path:
        return PROJECT_ROOT / "outputs" / self.output_name


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_int(*parts: object) -> int:
    data = "|".join(str(x) for x in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(data).digest()[:8], "little") % (2**31 - 1)


def _set_global_seed(seed: int) -> None:
    random.seed(int(seed))
    np.random.seed(int(seed))


def resolve_workers(n_tasks: int | None = None) -> int:
    """
    Resolve a reproducible process count.

    Priority:
    1. CRMD_WORKERS environment variable, if explicitly set.
    2. Conservative auto-detection from available CPU capacity.
    """
    explicit = os.getenv("CRMD_WORKERS")

    if explicit is not None:
        try:
            workers = int(explicit)
        except ValueError as exc:
            raise ValueError(f"CRMD_WORKERS must be a positive integer, got {explicit!r}.") from exc

        if workers < 1:
            raise ValueError("CRMD_WORKERS must be at least 1.")
    else:
        if hasattr(os, "sched_getaffinity"):
            available_cpus = len(os.sched_getaffinity(0))
        else:
            available_cpus = os.cpu_count() or 1

        workers = max(1, min(24, available_cpus - 4))

    if n_tasks is not None:
        workers = min(workers, max(1, n_tasks))

    return workers


def _workers_source() -> str:
    return "environment" if os.getenv("CRMD_WORKERS") is not None else "auto"


@lru_cache(maxsize=None)
def _trace_cached(horizon: int, seed: int, setting: str) -> ScenarioTrace:
    return build_scenario_trace(setting=setting, seed=int(seed), T=int(horizon), D_max=D_MAX, K=K)


def _family_and_role(setting: str) -> tuple[str, str]:
    if setting in PRIMARY_MATCHED_SETTINGS:
        return setting.split("_matched_")[0], "matched_primary"
    if setting.startswith("proxy_"):
        return "state_structural", "proxy_quality"
    if setting == "action_structural_stress":
        return "action_structural", "policy_dependent_stress"
    if setting.startswith("aligned_static"):
        return "fixed", "static_alignment"
    if setting.startswith("zero"):
        return "zero", "static_alignment"
    return "unknown", "unknown"


def _make_agent(method: str, trace: ScenarioTrace, horizon: int):
    cfg = trace.delay_cfg
    if method == "oracle":
        return OracleAgent(K)
    if method == "naive":
        return NaiveAgent(K)
    if method == "naive_ewma":
        return NaiveEWMAAgent(K, ewma_mu=float(os.environ.get("NAIVE_EWMA_MU", "0.98")))
    if method == "delayed_ucb":
        return DelayedUCBAgent(K)
    if method == "delayed_exp3":
        return DelayedEXP3Agent(K)
    if method == "sliding_window_W250":
        return SlidingWindowAgent(K, window=int(os.environ.get("EXP1_WINDOW", "250")))
    if method == "anonymous_delayed":
        return AnonymousDelayedAgent(K)
    if method == "causal_labeled":
        return CausalLabeledAgent(K)
    scenario_cfg = scenario_definitions()[trace.setting]
    state_kwargs = {
        "state_process": trace.state_process,
        "context_noise_sd": float(scenario_cfg.get("context_noise_sd", CONTEXT_NOISE_SD)),
        "fixed_state": trace.fixed_state,
    }
    if method == "causal_em":
        return CausalEMAgent(
            K, delay_cfg=cfg, T=horizon, D_max=D_MAX,
            misspecified_delay_model=False, L=D_MAX + 1, **state_kwargs,
        )
    if method == "causal_em_misspecified":
        return CausalEMAgent(
            K, delay_cfg=cfg, T=horizon, D_max=D_MAX,
            misspecified_delay_model=True, L=D_MAX + 1, **state_kwargs,
        )
    if method == "proxy":
        # The filter receives the proxy observation path; its documented noise
        # level includes both X-observation noise and the configured extra proxy
        # noise.  This is explicit proxy quality, not a terminal reconstruction.
        extra = float(scenario_cfg.get("proxy_extra_noise_sd", 0.0))
        obs_sd = float(np.sqrt(CONTEXT_NOISE_SD**2 + extra**2))
        return ProxyAgent(
            K=K, T=horizon, delay=cfg, D_max=D_MAX,
            observation_noise_sd=obs_sd, L=D_MAX + 1, sigma=1.0, **state_kwargs,
        )
    raise ValueError(f"unknown method {method}")


def _observed_arrivals(arrivals: list[dict[str, Any]], regime: str, label_rng: np.random.Generator) -> list[dict[str, Any]]:
    exposed: list[dict[str, Any]] = []
    label_rate = float(os.environ.get("LABEL_RATE_MIXTURE", "0.30"))
    for item in arrivals:
        row: dict[str, Any] = {"loss": float(item["loss"])}
        labelled = regime == "labelled" or (regime == "mixture_labelled" and bool(label_rng.random() < label_rate))
        if labelled:
            row.update({
                "src_a": int(item["src_a"]),
                "src_t": int(item["src_t"]),
                "src_x": float(item["src_x"]),
            })
        exposed.append(row)
    return exposed


def _safe_mean(values: Iterable[float]) -> float:
    vals = np.asarray(list(values), dtype=float)
    vals = vals[np.isfinite(vals)]
    return float(vals.mean()) if vals.size else float("nan")


def _ci95(values: pd.Series) -> tuple[int, float, float, float, float]:
    vals = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    n = int(vals.size)
    if not n:
        return 0, float("nan"), float("nan"), float("nan"), float("nan")
    mean = float(vals.mean())
    se = float(vals.std(ddof=1) / np.sqrt(n)) if n > 1 else 0.0
    return n, mean, se, mean - 1.96 * se, mean + 1.96 * se


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _clean_output_root(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    for sub in ("raw", "summaries", "tables", "metadata", "checks", "figures/data", "figures/png", "figures/pdf", "figures/metadata"):
        (root / sub).mkdir(parents=True, exist_ok=True)


def _write_run_state(root: Path, status: str, **kwargs: Any) -> None:
    _write_json(root / "run_log.json", {"project_id": PROJECT_ID, "status": status, "updated_at": _utc_now(), **kwargs})


def _assignment_metrics(agent, true_arrivals: list[dict[str, Any]]) -> dict[str, list[float] | int]:
    soft_mass: list[float] = []
    top1: list[float] = []
    entropy: list[float] = []
    labelled = 0
    unlabelled = 0
    for event in agent.pop_assignment_events():
        idx = int(event["arrival_index"])
        if idx < 0 or idx >= len(true_arrivals):
            continue
        if bool(event.get("labelled", False)):
            labelled += 1
            continue
        unlabelled += 1
        source_t = int(true_arrivals[idx]["src_t"])
        candidates = np.asarray(event.get("candidate_source_times", []), dtype=int)
        posterior = np.asarray(event.get("posterior", []), dtype=float)
        if posterior.size == 0 or candidates.size != posterior.size:
            continue
        positions = np.flatnonzero(candidates == source_t)
        mass = float(posterior[int(positions[0])]) if len(positions) else 0.0
        soft_mass.append(mass)
        top1.append(float(int(candidates[int(np.argmax(posterior))] == source_t)))
        entropy.append(float(event.get("assignment_entropy", np.nan)))
    return {"soft_mass": soft_mass, "top1": top1, "entropy": entropy, "labelled": labelled, "unlabelled": unlabelled}


def _run_one(
    seed: int,
    setting: str,
    regime: str,
    method: str,
    horizon: int,
    raw_writers: dict[str, csv.DictWriter] | None = None,
) -> dict[str, Any]:
    trace = _trace_cached(int(horizon), int(seed), str(setting))
    env = ToyDelayedEnv(T=horizon, K=K, D_max=D_MAX, trace=trace, env_seed=_stable_int("env", seed, setting, method))
    # Proxy-quality settings share the learner random tape within a seed/regime.
    # Their only intended exogenous difference is proxy observation quality.
    learner_setting = "proxy_quality_shared" if (method == "proxy" and setting in {"state_structural_matched_15", "proxy_good_matched_15", "proxy_bad_matched_15"}) else setting
    _set_global_seed(_stable_int("learner", seed, learner_setting, regime, method))
    agent = _make_agent(method, trace, horizon)
    agent.reset()
    # Visibility is exogenous and method-invariant for a seed × setting × regime.
    label_rng = np.random.default_rng(_stable_int("label_visibility", seed, setting, regime))

    actions: list[int] = []
    cumulative_regret = 0.0
    observed_delays: list[int] = []
    source_state_diffs: list[float] = []
    source_context_diffs: list[float] = []
    ranking_reversals: list[float] = []
    proxy_errors: list[float] = []
    soft_masses: list[float] = []
    soft_top1: list[float] = []
    assignment_entropy: list[float] = []
    n_labelled_arrivals = 0
    n_unlabelled_arrivals = 0
    n_censored = 0

    trace_every = max(1, int(os.environ.get("EXP1_TRACE_EVERY", "25")))
    for t in range(int(horizon)):
        state = float(env.step_state())
        context = float(env.context_at(t))
        proxy_obs = float(env.proxy_observation_at(t))
        agent.observe_context(context, t, proxy_obs)
        action = int(agent.act(env if method == "oracle" else None, t, context))
        actions.append(action)
        regret = float(env.conditional_regret_at_t(action, context))
        cumulative_regret += regret

        schedule = env.step_schedule(action, t)
        if bool(schedule["is_censored"]):
            n_censored += 1
        if raw_writers and "schedule" in raw_writers:
            raw_writers["schedule"].writerow({"run_id": f"seed{seed}_{setting}_{regime}_{method}", "seed": seed, "delay_setting": setting, "regime": regime, "method": method, **schedule})

        true_arrivals = env.pop_arrivals(t)
        visible_arrivals = _observed_arrivals(true_arrivals, regime, label_rng)
        agent.observe(None, t, action, context, visible_arrivals)
        per_batch = _assignment_metrics(agent, true_arrivals)
        soft_masses.extend(per_batch["soft_mass"])
        soft_top1.extend(per_batch["top1"])
        assignment_entropy.extend(per_batch["entropy"])
        # Label-visibility counts are collected below from the declared observed
        # feedback stream.  Assignment events are used only for posterior metrics.

        for original, visible in zip(true_arrivals, visible_arrivals):
            observed_delays.append(int(original["delay_tau"]))
            src_t = int(original["src_t"])
            source_state_diffs.append(abs(float(original["src_s"]) - state))
            source_context_diffs.append(abs(float(original["src_x"]) - context))
            ranking_reversals.append(float(int(env.optimal_action_from_context(float(original["src_x"])) != env.optimal_action_from_context(context))))
            if "src_a" in visible:
                n_labelled_arrivals += 1
            else:
                n_unlabelled_arrivals += 1
            if raw_writers and "arrival" in raw_writers:
                raw_writers["arrival"].writerow({
                    "run_id": f"seed{seed}_{setting}_{regime}_{method}", "seed": seed, "delay_setting": setting,
                    "regime": regime, "method": method, "clock_t": t, "arrival_t": int(original["arrival_t"]),
                    "source_t": src_t, "source_action": int(original["src_a"]), "source_state": float(original["src_s"]),
                    "source_context": float(original["src_x"]), "arrival_context": context,
                    "loss": float(original["loss"]), "delay_tau": int(original["delay_tau"]), "label_observed": int("src_a" in visible),
                })
        estimate = agent.proxy_state_estimate()
        if estimate is not None:
            proxy_errors.append(abs(float(estimate) - state))
        if raw_writers and "step" in raw_writers and (t % trace_every == 0 or t == horizon - 1):
            raw_writers["step"].writerow({
                "run_id": f"seed{seed}_{setting}_{regime}_{method}", "seed": seed, "delay_setting": setting,
                "regime": regime, "method": method, "t": t, "state": state, "context": context,
                "action_selected": action, "instantaneous_contextual_regret": regret,
                "cumulative_contextual_regret": cumulative_regret, "arrivals_observed": len(true_arrivals),
            })

    family, role = _family_and_role(setting)
    counts = np.bincount(np.asarray(actions, dtype=int), minlength=K) if actions else np.zeros(K, dtype=int)
    probs = counts / max(1, counts.sum())
    action_entropy = float(-np.sum(probs[probs > 0] * np.log(probs[probs > 0])))
    action_switch = float(np.mean(np.asarray(actions[1:]) != np.asarray(actions[:-1]))) if len(actions) > 1 else 0.0
    source_acc = _safe_mean(soft_top1)
    true_mass = _safe_mean(soft_masses)
    if method == "causal_labeled" and regime == "labelled":
        source_acc, true_mass = 1.0, 1.0
    observed_n = len(observed_delays)
    run_id = f"seed{seed}_{setting}_{regime}_{method}"
    em_delay_likelihood = getattr(agent, "delay_likelihood_name", "not_applicable")
    labelled_feature_alignment_max = (
        float(agent.labelled_feature_alignment_max())
        if hasattr(agent, "labelled_feature_alignment_max") else float("nan")
    )
    return {
        "experiment_id": PROJECT_ID,
        "run_id": run_id,
        "seed": int(seed),
        "delay_setting": setting,
        "delay_family": family,
        "setting_role": role,
        "policy_dependent_delay": bool(trace.policy_dependent_delay),
        "regime": regime,
        "method": method,
        "T": int(horizon),
        "K": int(K),
        "D_max": int(D_MAX),
        "context_observed_by_all": True,
        "regret_comparator": "context_information_oracle",
        "final_Rc": float(cumulative_regret),
        "mean_delay": _safe_mean(observed_delays),
        "median_delay": float(np.median(observed_delays)) if observed_delays else float("nan"),
        "p90_delay": float(np.quantile(observed_delays, 0.9)) if observed_delays else float("nan"),
        "trace_observed_mean_delay": float(trace.observed_mean_delay),
        "delay_calibration_target": trace.calibration_target,
        "delay_calibration_metric": trace.calibration_metric,
        "arrival_rate": float(observed_n / max(1, horizon)),
        "censor_ratio": float(n_censored / max(1, horizon)),
        "ranking_reversal_rate": _safe_mean(ranking_reversals),
        "source_state_mismatch_mean": _safe_mean(source_state_diffs),
        "source_context_mismatch_mean": _safe_mean(source_context_diffs),
        "proxy_state_error_mean": _safe_mean(proxy_errors),
        "em_delay_likelihood": em_delay_likelihood,
        "labelled_feature_alignment_max": labelled_feature_alignment_max,
        "soft_attribution_true_mass": true_mass,
        "soft_attribution_top1_accuracy": source_acc,
        "source_assignment_accuracy": source_acc,
        "assignment_entropy": _safe_mean(assignment_entropy),
        "attribution_error": float(1.0 - true_mass) if np.isfinite(true_mass) else float("nan"),
        "n_soft_assignment_events": int(len(soft_masses)),
        "n_labelled_arrivals": int(n_labelled_arrivals),
        "n_unlabelled_arrivals": int(n_unlabelled_arrivals),
        "n_observed_arrivals": int(observed_n),
        "effective_feedback_units": float(agent.feedback_units),
        "action_switching_rate": action_switch,
        "action_entropy": action_entropy,
        "delay_path_id": f"shared_{seed}_{setting}" if not trace.policy_dependent_delay else f"policy_dependent_{seed}_{setting}_{method}",
        "config_hash": compute_config_hash({"setting": setting, "regime": regime, "method": method, "T": horizon, "K": K, "Dmax": D_MAX}),
    }


def _run_task(task: Task, horizon: int) -> dict[str, Any]:
    seed, setting, regime, method = task
    return _run_one(int(seed), setting, regime, method, int(horizon), None)


def _make_summaries(seed: pd.DataFrame, root: Path) -> None:
    seed.to_csv(root / "summaries" / "seed_summary.csv", index=False)
    keys = ["delay_setting", "delay_family", "setting_role", "policy_dependent_delay", "regime", "method"]
    rows = []
    diagnostic_rows = []
    for group_keys, frame in seed.groupby(keys, dropna=False):
        base = dict(zip(keys, group_keys))
        n, mean, se, lo, hi = _ci95(frame["final_Rc"])
        rows.append({
            "experiment_id": PROJECT_ID, **base, "n_seeds": n,
            "mean_final_Rc": mean, "se_final_Rc": se, "ci95_low": lo, "ci95_high": hi,
            "mean_delay": _safe_mean(frame["mean_delay"]), "trace_observed_mean_delay": _safe_mean(frame["trace_observed_mean_delay"]),
            "arrival_rate": _safe_mean(frame["arrival_rate"]),
        })
        diagnostic_rows.append({
            "experiment_id": PROJECT_ID, **base, "n_seeds": n,
            **{col: _safe_mean(frame[col]) for col in (
                "mean_delay", "trace_observed_mean_delay", "arrival_rate", "censor_ratio", "ranking_reversal_rate",
                "source_state_mismatch_mean", "source_context_mismatch_mean", "proxy_state_error_mean",
                "soft_attribution_true_mass", "soft_attribution_top1_accuracy", "assignment_entropy", "attribution_error",
                "effective_feedback_units", "n_observed_arrivals", "n_soft_assignment_events",
            )},
        })
    method_df = pd.DataFrame(rows)
    diag_df = pd.DataFrame(diagnostic_rows)
    method_df.to_csv(root / "summaries" / "method_summary.csv", index=False)
    method_df.to_csv(root / "summaries" / "method_comparison_summary.csv", index=False)
    diag_df.to_csv(root / "summaries" / "diagnostic_summary.csv", index=False)
    matched = method_df[method_df["delay_setting"].isin(PRIMARY_MATCHED_SETTINGS)].copy()
    matched.to_csv(root / "summaries" / "matched_mean_delay_summary.csv", index=False)

    paired = []
    for (setting, regime), frame in seed.groupby(["delay_setting", "regime"]):
        pivot = frame.pivot_table(index="seed", columns="method", values="final_Rc", aggfunc="first")
        for base_method in ("naive", "delayed_ucb", "delayed_exp3"):
            if base_method not in pivot:
                continue
            for method in METHODS:
                if method not in pivot or method == base_method:
                    continue
                n, mean, se, lo, hi = _ci95((pivot[base_method] - pivot[method]).dropna())
                paired.append({"delay_setting": setting, "regime": regime, "baseline": base_method, "method": method,
                               "n_pairs": n, "paired_mean_diff": mean, "paired_se": se, "paired_ci95_low": lo, "paired_ci95_high": hi})
    pd.DataFrame(paired).to_csv(root / "summaries" / "paired_tests.csv", index=False)
    # Keep a compact bootstrap interface for downstream LaTex/table consumers.
    boot = []
    for keys_, frame in seed.groupby(["delay_setting", "regime", "method"]):
        vals = pd.to_numeric(frame["final_Rc"], errors="coerce").dropna().to_numpy(float)
        rng = np.random.default_rng(_stable_int("bootstrap", *keys_))
        if len(vals) <= 1:
            lo = hi = float(vals[0]) if len(vals) else float("nan")
        else:
            draws = vals[rng.integers(0, len(vals), size=(1000, len(vals)))].mean(axis=1)
            lo, hi = np.quantile(draws, [0.025, 0.975])
        boot.append({"delay_setting": keys_[0], "regime": keys_[1], "method": keys_[2], "bootstrap_ci95_low": lo, "bootstrap_ci95_high": hi, "n": len(vals)})
    pd.DataFrame(boot).to_csv(root / "summaries" / "bootstrap_ci.csv", index=False)
    for name, df in {"table_exp1_results": method_df, "table_exp1_diagnostics": diag_df, "table_exp1_matched_delay": matched}.items():
        df.to_csv(root / "tables" / f"{name}.csv", index=False)


def _artifact_rows(root: Path) -> list[dict[str, Any]]:
    required = [
        "metadata/run_manifest.json", "metadata/design_manifest.csv", "metadata/scenario_trace_manifest.csv", "metadata/environment.txt",
        "summaries/seed_summary.csv", "summaries/method_summary.csv", "summaries/diagnostic_summary.csv",
        "figures/data/fig_exp1_validity_boundary_data.csv", "figures/png/fig_exp1_validity_boundary.png", "figures/pdf/fig_exp1_validity_boundary.pdf",
        "figures/data/fig_exp1_same_mean_delay_data.csv", "figures/png/fig_exp1_same_mean_delay.png", "figures/pdf/fig_exp1_same_mean_delay.pdf",
        "figures/data/fig_exp1_attribution_diagnostics_data.csv", "figures/png/fig_exp1_attribution_diagnostics.png", "figures/pdf/fig_exp1_attribution_diagnostics.pdf",
        "figures/data/fig_exp1_proxy_quality_data.csv", "figures/png/fig_exp1_proxy_quality.png", "figures/pdf/fig_exp1_proxy_quality.pdf",
    ]
    return [{"relative_path": rel, "required": True, "exists": (root / rel).exists(), "bytes": (root / rel).stat().st_size if (root / rel).exists() else 0} for rel in required]


def _write_metadata(
    options: RunOptions,
    seed_df: pd.DataFrame,
    design_df: pd.DataFrame,
    trace_rows: list[dict[str, Any]],
    status: str,
    runtime_meta: dict[str, Any],
    error: str = "",
) -> None:
    root = options.output_root
    expected = len(options.seeds) * len(SETTINGS) * len(REGIMES) * len(METHODS)
    payload = {
        "project_id": PROJECT_ID, "status": "PASSED" if status == "completed" else "FAILED", "backend_status": status,
        "error": error, "mode": options.mode, "is_smoke": bool(options.smoke), "paper_result": False,
        "n_seeds": len(options.seeds), "horizon": options.horizon, "expected_runs": expected, "completed_runs": len(seed_df),
        "settings": list(SETTINGS), "methods": list(METHODS), "regimes": list(REGIMES),
        **runtime_meta,
        "information_structure": "all learners observe X_t; comparator is the conditional-risk argmin_a E[loss(a,S_t)|X_t]",
        "primary_delay_contract": "pre-generated shared state/context/delay paths; matched by realised uncensored finite-horizon mean delay",
        "action_dependent_delay_contract": "policy-dependent stress test; excluded from same-mean-delay primary claim",
        "structural_em_contract": "default EM integrates P(D=d|observable source feature) under the Gaussian AR(1) state posterior by binned Gauss-Hermite quadrature; stationary geometric EM is an explicit ablation",
        "proxy_feature_contract": "proxy action selection, labelled source updates, and unlabelled candidate updates all use the saved source-time Kalman proxy feature",
        "created_at_utc": _utc_now(),
    }
    _write_json(root / "metadata" / "run_manifest.json", payload)
    design_df.to_csv(root / "metadata" / "design_manifest.csv", index=False)
    pd.DataFrame(trace_rows).to_csv(root / "metadata" / "scenario_trace_manifest.csv", index=False)
    with (root / "metadata" / "environment.txt").open("w", encoding="utf-8") as fh:
        fh.write(f"python={sys.version}\nplatform={platform.platform()}\nnumpy={np.__version__}\n")
        fh.write("estimand=context-information oracle excess conditional risk\n")
        fh.write("primary paths=pre-generated and shared across methods\n")
    rows = _artifact_rows(root)
    pd.DataFrame(rows).to_csv(root / "metadata" / "artifacts_manifest.csv", index=False)
    pd.DataFrame(rows).to_csv(root / "manifest.csv", index=False)
    _write_json(root / "manifest.json", {"artifacts": rows, "runtime": runtime_meta})


def _open_writer(path: Path, fields: list[str]) -> tuple[Any, csv.DictWriter]:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    return handle, writer


def run(mode: str, raw_log_mode: str | None = None, smoke: bool = False, output_tag: str | None = None) -> int:
    if mode not in {"fast", "full"}:
        raise ValueError("mode must be fast or full")
    raw_log_mode = raw_log_mode or ("summary_only" if mode == "fast" else "full")
    options = RunOptions(mode=mode, raw_log_mode=raw_log_mode, smoke=smoke, output_tag=output_tag)
    root = options.output_root
    _clean_output_root(root)

    trace_rows: list[dict[str, Any]] = []
    tasks: list[Task] = []
    for seed in options.seeds:
        for setting in SETTINGS:
            trace = _trace_cached(options.horizon, int(seed), setting)
            trace_rows.append({"seed": seed, "delay_setting": setting, "delay_path_id": f"shared_{seed}_{setting}" if not trace.policy_dependent_delay else f"policy_dependent_{seed}_{setting}",
                               "policy_dependent_delay": trace.policy_dependent_delay, "observed_mean_delay": trace.observed_mean_delay,
                               "observed_count": trace.observed_count, "calibration_target": trace.calibration_target,
                               "calibration_metric": trace.calibration_metric, "delay_cfg": json.dumps(trace.delay_cfg, default=lambda x: np.asarray(x).tolist())})
            for regime in REGIMES:
                for method in METHODS:
                    tasks.append((int(seed), setting, regime, method))

    expected = len(tasks)
    workers = resolve_workers(n_tasks=expected)
    runtime_meta = {
        "workers": workers,
        "cpu_count": os.cpu_count(),
        "workers_source": _workers_source(),
    }
    _write_run_state(root, "RUNNING", mode=mode, is_smoke=smoke, expected_runs=expected, completed_runs=0, **runtime_meta)
    print(f"[runtime] workers={workers}, tasks={expected}", flush=True)

    handles: list[Any] = []
    writers: dict[str, csv.DictWriter] = {}
    if raw_log_mode == "full":
        h, writers["schedule"] = _open_writer(root / "raw" / "delay_schedule.csv", ["run_id", "seed", "delay_setting", "regime", "method", "source_t", "source_state", "source_context", "source_action", "source_loss", "source_optimal_action", "delay_tau", "delay_hazard", "arrival_t", "is_censored", "censor_reason"]); handles.append(h)
        h, writers["arrival"] = _open_writer(root / "raw" / "arrival_log.csv", ["run_id", "seed", "delay_setting", "regime", "method", "clock_t", "arrival_t", "source_t", "source_action", "source_state", "source_context", "arrival_context", "loss", "delay_tau", "label_observed"]); handles.append(h)
        h, writers["step"] = _open_writer(root / "raw" / "step_log.csv", ["run_id", "seed", "delay_setting", "regime", "method", "t", "state", "context", "action_selected", "instantaneous_contextual_regret", "cumulative_contextual_regret", "arrivals_observed"]); handles.append(h)

    seed_rows: list[dict[str, Any]] = []
    design_rows: list[dict[str, Any]] = []
    try:
        if workers == 1:
            for task in tasks:
                seed, setting, regime, method = task
                idx = len(seed_rows) + 1
                try:
                    row = _run_one(int(seed), setting, regime, method, options.horizon, writers if writers else None)
                    seed_rows.append(row)
                    design_rows.append({"seed": seed, "scenario": setting, "condition": regime, "method": method, "horizon": options.horizon, "status": "completed", "failure_reason": ""})
                except Exception as exc:
                    design_rows.append({"seed": seed, "scenario": setting, "condition": regime, "method": method, "horizon": options.horizon, "status": "failed", "failure_reason": f"{type(exc).__name__}: {exc}"})
                    raise
                if idx % max(1, min(12, expected)) == 0 or idx == expected:
                    pd.DataFrame(seed_rows).to_csv(root / "raw" / "seed_level_results.csv", index=False)
                    _write_run_state(root, "RUNNING", mode=mode, is_smoke=smoke, expected_runs=expected, completed_runs=idx, **runtime_meta)
                    print(f"[EXP1 {options.output_name}] completed {idx}/{expected} runs", flush=True)
        else:
            if writers:
                print("[runtime] detailed raw logs are written only when workers=1; seed-level outputs remain complete", flush=True)
            with ProcessPoolExecutor(max_workers=workers) as executor:
                for idx, (task, row) in enumerate(zip(tasks, executor.map(partial(_run_task, horizon=options.horizon), tasks)), start=1):
                    seed, setting, regime, method = task
                    seed_rows.append(row)
                    design_rows.append({"seed": seed, "scenario": setting, "condition": regime, "method": method, "horizon": options.horizon, "status": "completed", "failure_reason": ""})
                    if idx % max(1, min(12, expected)) == 0 or idx == expected:
                        pd.DataFrame(seed_rows).to_csv(root / "raw" / "seed_level_results.csv", index=False)
                        _write_run_state(root, "RUNNING", mode=mode, is_smoke=smoke, expected_runs=expected, completed_runs=idx, **runtime_meta)
                        print(f"[EXP1 {options.output_name}] completed {idx}/{expected} runs", flush=True)
        seed_df = pd.DataFrame(seed_rows)
        design_df = pd.DataFrame(design_rows)
        seed_df.to_csv(root / "raw" / "seed_level_results.csv", index=False)
        _make_summaries(seed_df, root)
        plot_exp1_bundles(seed_df, root)
        _write_metadata(options, seed_df, design_df, trace_rows, "completed", runtime_meta)
        _write_run_state(root, "PASSED", mode=mode, is_smoke=smoke, expected_runs=expected, completed_runs=expected, **runtime_meta)
    except Exception as exc:
        seed_df = pd.DataFrame(seed_rows)
        design_df = pd.DataFrame(design_rows)
        if not seed_df.empty:
            seed_df.to_csv(root / "raw" / "seed_level_results.csv", index=False)
        _write_metadata(options, seed_df, design_df, trace_rows, "failed", runtime_meta, "".join(traceback.format_exception_only(type(exc), exc)).strip())
        _write_run_state(root, "FAILED", mode=mode, is_smoke=smoke, expected_runs=expected, completed_runs=len(seed_rows), error=repr(exc), **runtime_meta)
        print(f"[EXP1 {options.output_name}] FAILED after {len(seed_rows)}/{expected}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        for h in handles:
            h.close()

    from self_check import check_project
    return 0 if check_project(mode=mode, output_tag=options.output_name) else 1

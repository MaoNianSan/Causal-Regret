"""Sequential delayed-feedback engine and Exp4 task definitions."""

from __future__ import annotations

from typing import Any
import hashlib
import numpy as np

import config
from simulator import (
    Trace,
    generate_trace,
    measurement_diagnostics,
    observed_measurement,
    trace_diagnostics,
)
from policies import (
    ArrivalTimeNaiveUCB,
    NoisyOracleProxyDiagnostic,
    ObservableHistorySurrogate,
    ProxyLabelRecoveryUCB,
    ProxyOracleDiagnostic,
    SourceLabelledReferenceUCB,
)


def nested_label_mask(trace: Trace, q: float) -> np.ndarray:
    """Nested source-ID retention mask; retention is revealed only at arrival."""
    return trace.label_uniforms < float(q)


def _context_history(trace: Trace) -> np.ndarray:
    context_proxy = observed_measurement(trace, config.CONTEXT_PROXY_SIGMA)
    return np.argmin(
        ((context_proxy[:, None, :] - trace.action_centers[None, :, :]) ** 2).sum(
            axis=2
        ),
        axis=1,
    ).astype(int)


def _policy(method_id: str, trace: Trace, proxy_sigma: float, n_contexts: int):
    if method_id == "arrival_time_naive":
        return ArrivalTimeNaiveUCB(config.K_ACTIONS, n_contexts)
    if method_id == "source_labelled_reference":
        return SourceLabelledReferenceUCB(config.K_ACTIONS, n_contexts)
    if method_id == "proxy_label_recovery":
        return ProxyLabelRecoveryUCB(
            config.K_ACTIONS,
            n_contexts,
            observed_measurement(trace, proxy_sigma),
            config.MAX_DELAY,
        )
    if method_id == "observable_history_surrogate":
        return ObservableHistorySurrogate(config.K_ACTIONS, n_contexts)
    if method_id == "proxy_noisy_oracle_diagnostic":
        return NoisyOracleProxyDiagnostic(
            trace.action_centers, observed_measurement(trace, proxy_sigma)
        )
    if method_id == "proxy_oracle_diagnostic":
        return ProxyOracleDiagnostic(trace.action_centers, trace.states)
    raise ValueError(f"unknown method id {method_id}")


def _method_fields(method_id: str) -> dict[str, Any]:
    spec = config.method_spec(method_id)
    return {
        "method_id": method_id,
        "method_display_name": spec["display"],
        "information_interface": spec["information_interface"],
        "reference_role": spec["reference_role"],
        "diagnostic_only": bool(spec["diagnostic_only"]),
        "deployable": bool(spec["deployable"]),
    }


def run_online_policy(
    trace: Trace,
    method_id: str,
    *,
    q: float = 0.0,
    proxy_sigma: float = config.DEFAULT_PROXY_SIGMA,
) -> dict[str, Any]:
    """Run one route under action-before-arrival semantics.

    At round ``u`` the current action is selected first.  Only then can feedback
    from sources ``s < u`` be processed.  For anonymous feedback, the hidden source
    index is intentionally stripped before the policy call.
    """
    contexts = _context_history(trace)
    policy = _policy(method_id, trace, proxy_sigma, config.K_ACTIONS)
    actions = np.zeros(trace.T, dtype=int)
    regrets = np.zeros(trace.T, dtype=float)
    retention_mask = nested_label_mask(trace, q)

    labelled_arrivals = 0
    anonymous_arrivals = 0
    total_arrivals = 0
    wrong_assignment_events = 0
    event_time_gaps: list[int] = []

    for t in range(trace.T):
        context = int(contexts[t])
        action = policy.choose(t, context)
        actions[t] = action
        losses_t = trace.potential_losses[t]
        regrets[t] = float(losses_t[action] - np.min(losses_t))

        full_events = [
            (source, float(trace.potential_losses[source, actions[source]]))
            for source in trace.arrivals[t]
        ]
        total_arrivals += len(full_events)
        anonymous_losses = [loss for _, loss in full_events]

        if method_id == "arrival_time_naive":
            wrong_assignment_events += sum(
                int(actions[source] != action) for source, _ in full_events
            )
            policy.observe(
                current_action=action,
                current_context=context,
                anonymous_losses=anonymous_losses,
            )
        elif method_id == "source_labelled_reference":
            labelled_arrivals += len(full_events)
            event_time_gaps.extend(t - source for source, _ in full_events)
            policy.observe(
                labelled_events=full_events,
                action_history=actions,
                context_history=contexts,
            )
        elif method_id == "observable_history_surrogate":
            policy.observe(
                current_action=action,
                current_context=context,
                anonymous_losses=anonymous_losses,
            )
        elif method_id == "proxy_label_recovery":
            labelled_events = [
                (source, loss) for source, loss in full_events if retention_mask[source]
            ]
            anonymous = [
                loss for source, loss in full_events if not retention_mask[source]
            ]
            labelled_arrivals += len(labelled_events)
            anonymous_arrivals += len(anonymous)
            event_time_gaps.extend(t - source for source, _ in labelled_events)
            # The policy gets no source IDs for ``anonymous`` losses.
            policy.observe(
                arrival_t=t,
                labelled_events=labelled_events,
                anonymous_losses=anonymous,
                action_history=actions,
                context_history=contexts,
            )
        else:
            policy.observe()

    proxy_error = np.nan
    proxy_reversal = np.nan
    proxy_distortion = np.nan
    if method_id in {"proxy_noisy_oracle_diagnostic", "proxy_label_recovery"}:
        proxy_error, proxy_reversal, proxy_distortion = measurement_diagnostics(
            trace, proxy_sigma
        )
    elif method_id == "proxy_oracle_diagnostic":
        proxy_error = 0.0
        proxy_reversal = 0.0
        proxy_distortion = 0.0

    eval_regrets = regrets[config.WARMUP_T :]
    diagnostics = trace_diagnostics(trace)
    result: dict[str, Any] = {
        "experiment_id": config.EXPERIMENT_ID,
        "seed": trace.seed,
        "source_label_rate_q": float(q),
        "proxy_noise_sigma": float(proxy_sigma),
        "causal_regret_per_round": float(eval_regrets.mean()),
        "causal_regret_all_rounds": float(regrets.mean()),
        "final_causal_regret": float(regrets.sum()),
        "n_eval_rounds": int(len(eval_regrets)),
        "labelled_arrivals": int(labelled_arrivals),
        "anonymous_arrivals": int(anonymous_arrivals),
        "total_arrivals": int(total_arrivals),
        "labelled_arrival_fraction": (
            float(labelled_arrivals / total_arrivals) if total_arrivals else 0.0
        ),
        "min_label_arrival_gap": (
            int(min(event_time_gaps)) if event_time_gaps else np.nan
        ),
        "wrong_assignment_rate": (
            float(wrong_assignment_events / total_arrivals) if total_arrivals else 0.0
        ),
        "proxy_state_error_per_round": proxy_error,
        "proxy_ranking_reversal_rate": proxy_reversal,
        "absolute_proxy_distortion_per_round": proxy_distortion,
        "context_misclassification_rate": float(
            np.mean(contexts != np.argmin(trace.potential_losses, axis=1))
        ),
        "action_trace_sha256": hashlib.sha256(actions.tobytes()).hexdigest(),
        "proxy_observation_interface": (
            "simulator_emitted"
            if method_id != "proxy_oracle_diagnostic"
            else "latent_diagnostic_only"
        ),
        **_method_fields(method_id),
        **diagnostics,
    }
    return result


def _row(
    trace: Trace,
    subexperiment_id: str,
    setting_id: str,
    result: dict[str, Any],
    *,
    beta: float,
    notes: str = "",
) -> dict[str, Any]:
    return {
        "subexperiment_id": subexperiment_id,
        "setting_id": setting_id,
        "delay_state_coupling_beta": float(beta),
        "notes": notes,
        **result,
    }


def run_task(task: dict[str, Any]) -> list[dict[str, Any]]:
    """Picklable worker entry point.  Each task uses a deterministic trace."""
    seed = int(task["seed"])
    T = int(task["T"])
    kind = str(task["kind"])

    if kind == "proxy_diagnostic":
        trace = generate_trace(seed, T, config.DEFAULT_BETA)
        rows: list[dict[str, Any]] = []
        for sigma in config.PROXY_SIGMAS:
            result = run_online_policy(
                trace, "proxy_noisy_oracle_diagnostic", proxy_sigma=sigma
            )
            rows.append(
                _row(
                    trace,
                    "proxy_distortion_diagnostic",
                    f"sigma_{sigma:.2f}",
                    result,
                    beta=config.DEFAULT_BETA,
                )
            )
        result = run_online_policy(trace, "proxy_oracle_diagnostic", proxy_sigma=0.0)
        rows.append(
            _row(
                trace,
                "proxy_distortion_diagnostic",
                "proxy_oracle",
                result,
                beta=config.DEFAULT_BETA,
            )
        )
        result = run_online_policy(
            trace, "arrival_time_naive", proxy_sigma=config.DEFAULT_PROXY_SIGMA
        )
        rows.append(
            _row(
                trace,
                "baseline_reference",
                "arrival_time_baseline",
                result,
                beta=config.DEFAULT_BETA,
            )
        )
        return rows

    if kind == "source_label_sweep":
        q = float(task["q"])
        trace = generate_trace(seed, T, config.DEFAULT_BETA)
        rows = []
        for method_id in ["observable_history_surrogate", "proxy_label_recovery"]:
            result = run_online_policy(
                trace, method_id, q=q, proxy_sigma=config.DEFAULT_PROXY_SIGMA
            )
            rows.append(
                _row(
                    trace,
                    "source_label_sweep",
                    f"q_{q:.2f}_sigma_{config.DEFAULT_PROXY_SIGMA:.2f}",
                    result,
                    beta=config.DEFAULT_BETA,
                )
            )
        if np.isclose(q, 1.0):
            result = run_online_policy(
                trace,
                "source_labelled_reference",
                q=1.0,
                proxy_sigma=config.DEFAULT_PROXY_SIGMA,
            )
            rows.append(
                _row(
                    trace,
                    "source_label_sweep",
                    "q_1.00_source_labelled_reference",
                    result,
                    beta=config.DEFAULT_BETA,
                )
            )
        return rows

    if kind == "phase_grid":
        q = float(task["q"])
        sigma = float(task["sigma"])
        trace = generate_trace(seed, T, config.DEFAULT_BETA)
        result = run_online_policy(
            trace, "proxy_label_recovery", q=q, proxy_sigma=sigma
        )
        return [
            _row(
                trace,
                "recoverability_phase_map",
                f"q_{q:.2f}_sigma_{sigma:.2f}",
                result,
                beta=config.DEFAULT_BETA,
            )
        ]

    if kind == "delay_coupling":
        beta = float(task["beta"])
        trace = generate_trace(seed, T, beta)
        rows = []
        for method_id, q in [
            ("arrival_time_naive", 0.0),
            ("observable_history_surrogate", 0.0),
            ("proxy_label_recovery", 0.0),
            ("source_labelled_reference", 1.0),
        ]:
            result = run_online_policy(
                trace, method_id, q=q, proxy_sigma=config.DEFAULT_PROXY_SIGMA
            )
            rows.append(
                _row(
                    trace,
                    "delay_state_coupling_diagnostic",
                    f"beta_{beta:.2f}",
                    result,
                    beta=beta,
                )
            )
        return rows

    raise ValueError(f"unknown task kind {kind}")

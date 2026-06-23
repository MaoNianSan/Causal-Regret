from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import math
import random
import numpy as np


# ----------------------------------------------------------------------
# Exploration schedule
# ----------------------------------------------------------------------
def eps_schedule(t: int, eps0: float = 0.2, t0: int = 50, floor: float = 0.01) -> float:
    return max(floor, eps0 * math.sqrt(t0 / (t0 + t)))


# ----------------------------------------------------------------------
# Delayed feedback buffer
# ----------------------------------------------------------------------
class FeedbackBuffer:
    def __init__(self):
        self.q = defaultdict(list)

    def push(self, tau: int, payload: Any):
        self.q[tau].append(payload)

    def pop(self, t: int) -> List[Any]:
        return self.q.pop(t, [])


# ----------------------------------------------------------------------
# Oracle learner:
# full-information baseline that always plays the action minimizing
# the instantaneous loss under the current latent state S_t.
# ----------------------------------------------------------------------
class OracleLearner:
    def __init__(self):
        self.A = None

    def init(self, A: List[int]):
        self.A = A

    def choose_action(self, t: int, eps: float) -> int:
        # The chosen action is overridden inside run_one_seed
        # using env.oracle_action(S_t).
        return self.A[0]

    def on_arrivals(self, arrivals: List[Dict], current_action: int | None = None):
        # Oracle does not use delayed arrivals for learning.
        return

    def make_feedback_payload(
        self,
        t_gen: int,
        a: int,
        loss: float,
        src_state: float,
        src_optimal_action: int,
        delay_tau: int,
        arrival_t: int,
    ) -> Dict[str, Any]:
        return {
            "t_gen": t_gen,
            "src_a": a,
            "a": a,
            "loss": loss,
            "src_state": src_state,
            "src_optimal_action": src_optimal_action,
            "delay_tau": delay_tau,
            "arrival_t": arrival_t,
        }


# ----------------------------------------------------------------------
# Naive learner:
# ignores delay-induced attribution mismatch and treats all arrivals at
# time t as if they belonged to the current action context.
# ----------------------------------------------------------------------
class NaiveLearner:
    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self.A = None
        self.est_loss = defaultdict(float)
        self.cnt = defaultdict(int)

    def init(self, A: List[int]):
        self.A = A
        self.est_loss.clear()
        self.cnt.clear()

    def on_arrivals(self, arrivals: List[Dict], current_action: int | None = None):
        """
        Misattribution rule:
        all feedback arriving at time t is assigned to the current action a_t,
        regardless of the action that originally generated it.
        """
        if current_action is None:
            return

        for p in arrivals:
            loss = p["loss"]
            a = current_action
            self.cnt[a] += 1
            if self.cnt[a] == 1:
                self.est_loss[a] = loss
            else:
                self.est_loss[a] = (1 - self.alpha) * self.est_loss[
                    a
                ] + self.alpha * loss

    def choose_action(self, t: int, eps: float) -> int:
        unseen = [a for a in self.A if self.cnt[a] == 0]
        if unseen:
            return random.choice(unseen)
        if random.random() < eps:
            return random.choice(self.A)
        return min(self.A, key=lambda a: self.est_loss[a])

    def make_feedback_payload(
        self,
        t_gen: int,
        a: int,
        loss: float,
        src_state: float,
        src_optimal_action: int,
        delay_tau: int,
        arrival_t: int,
    ) -> Dict[str, Any]:
        return {
            "t_gen": t_gen,
            "src_a": a,
            "a": a,
            "loss": loss,
            "src_state": src_state,
            "src_optimal_action": src_optimal_action,
            "delay_tau": delay_tau,
            "arrival_t": arrival_t,
        }


# ----------------------------------------------------------------------
# Causal learner:
# delay-aware labelled learner that uses the true generating action
# carried by each arrived feedback item and updates action losses by EWMA.
# ----------------------------------------------------------------------
class CausalLearner:
    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self.A = None
        self.est_loss = defaultdict(float)
        self.cnt = defaultdict(int)

    def init(self, A: List[int]):
        self.A = A
        self.est_loss.clear()
        self.cnt.clear()

    def on_arrivals(self, arrivals: List[Dict], current_action: int | None = None):
        for p in arrivals:
            a = p["src_a"] if "src_a" in p else p["a"]
            loss = p["loss"]
            self.cnt[a] += 1
            if self.cnt[a] == 1:
                self.est_loss[a] = loss
            else:
                self.est_loss[a] = (1 - self.alpha) * self.est_loss[
                    a
                ] + self.alpha * loss

    def choose_action(self, t: int, eps: float) -> int:
        unseen = [a for a in self.A if self.cnt[a] == 0]
        if unseen:
            return random.choice(unseen)
        if random.random() < eps:
            return random.choice(self.A)
        return min(self.A, key=lambda a: self.est_loss[a])

    def make_feedback_payload(
        self,
        t_gen: int,
        a: int,
        loss: float,
        src_state: float,
        src_optimal_action: int,
        delay_tau: int,
        arrival_t: int,
    ) -> Dict[str, Any]:
        return {
            "t_gen": t_gen,
            "src_a": a,
            "a": a,
            "loss": loss,
            "src_state": src_state,
            "src_optimal_action": src_optimal_action,
            "delay_tau": delay_tau,
            "arrival_t": arrival_t,
        }


# ----------------------------------------------------------------------
# Result container for a single seed
# ----------------------------------------------------------------------
@dataclass
class SingleRunResult:
    regret: List[float]
    arrival_rate: List[float]
    step_rows: List[Dict[str, Any]]
    delay_rows: List[Dict[str, Any]]
    arrival_rows: List[Dict[str, Any]]
    diagnostic_rows: List[Dict[str, Any]]
    seed_summary: Dict[str, Any]


# ----------------------------------------------------------------------
# Single-seed simulation with hard delay truncation at D_max
# ----------------------------------------------------------------------
def run_one_seed(
    *,
    T: int,
    A: List[int],
    D_max: int,
    delay_sampler,
    delay_setting_name: str,
    method_name: str,
    run_id: str,
    env,
    learner,
    seed: int,
    delay_sequence: Optional[List[int]] = None,
) -> SingleRunResult:
    random.seed(seed)
    np.random.seed(seed)

    buf = FeedbackBuffer()
    learner.init(A)

    cum_regret = 0.0
    regret_list: List[float] = []

    scheduled_total = 0
    arrived_total = 0
    arrival_list: List[float] = []

    step_rows: List[Dict[str, Any]] = []
    delay_rows: List[Dict[str, Any]] = []
    arrival_rows: List[Dict[str, Any]] = []
    diagnostic_rows: List[Dict[str, Any]] = []

    delays: List[int] = []
    instant_regrets: List[float] = []

    for t in range(1, T + 1):
        eps = eps_schedule(t)
        a_t = learner.choose_action(t, eps)

        S_t = env.state()
        a_star = env.oracle_action(S_t)

        if isinstance(learner, OracleLearner):
            a_t = a_star

        loss_t = env.true_loss(a_t, S_t)

        if delay_sequence is not None:
            d = delay_sequence[t - 1]
        else:
            d = delay_sampler(t)
        if d < 0:
            raise ValueError(f"delay must be nonnegative, got {d}")

        scheduled_total += 1
        arrival_t = t + d
        payload = learner.make_feedback_payload(
            t_gen=t,
            a=a_t,
            loss=loss_t,
            src_state=S_t,
            src_optimal_action=a_star,
            delay_tau=d,
            arrival_t=arrival_t,
        )

        censored = False
        censor_reason = "none"
        if d > D_max:
            censored = True
            censor_reason = "delay_exceeds_Dmax"
        elif arrival_t > T:
            censored = True
            censor_reason = "arrival_out_of_horizon"

        if not censored:
            buf.push(arrival_t, payload)

        delay_rows.append(
            {
                "run_id": run_id,
                "seed": seed,
                "source_t": t,
                "delay_setting": delay_setting_name,
                "method": method_name,
                "source_state": S_t,
                "source_action": a_t,
                "source_optimal_action": a_star,
                "source_loss": loss_t,
                "delay_tau": d,
                "arrival_t": arrival_t if d <= D_max else None,
                "is_censored": censored,
                "censor_reason": censor_reason,
            }
        )

        arrivals_t = buf.pop(t)
        arrived_total += len(arrivals_t)

        learner.on_arrivals(arrivals_t, current_action=a_t)

        loss_star = env.true_loss(a_star, S_t)
        instant_regret = loss_t - loss_star
        cum_regret += instant_regret
        regret_list.append(cum_regret)
        instant_regrets.append(instant_regret)

        arrival_rate_t = arrived_total / max(1, scheduled_total)
        arrival_list.append(arrival_rate_t)

        if arrivals_t:
            distances = []
            reversals = []
            for payload_item in arrivals_t:
                source_state = payload_item["src_state"]
                source_optimal = payload_item["src_optimal_action"]
                source_action = payload_item["src_a"]
                observed_loss = payload_item["loss"]
                current_state = S_t
                ranking_reversal = 1 if source_optimal != a_star else 0
                distances.append(abs(current_state - source_state))
                reversals.append(ranking_reversal)
                arrival_rows.append(
                    {
                        "run_id": run_id,
                        "seed": seed,
                        "clock_t": t,
                        "source_t": payload_item["t_gen"],
                        "delay_tau": payload_item["delay_tau"],
                        "arrival_t": payload_item["arrival_t"],
                        "method": method_name,
                        "delay_setting": delay_setting_name,
                        "batch_size_at_clock_t": len(arrivals_t),
                        "observed_loss": observed_loss,
                        "source_action": source_action,
                        "current_action": a_t,
                        "current_state": current_state,
                        "source_state": source_state,
                        "source_state_distance": abs(current_state - source_state),
                        "source_optimal_action": source_optimal,
                        "current_optimal_action": a_star,
                        "ranking_reversal": ranking_reversal,
                    }
                )
            arrival_batch_size = len(arrivals_t)
            mean_source_state_distance = sum(distances) / len(distances)
            ranking_reversal_rate_at_t = sum(reversals) / len(reversals)
        else:
            arrival_batch_size = 0
            mean_source_state_distance = "NA"
            ranking_reversal_rate_at_t = "NA"

        diagnostic_rows.append(
            {
                "run_id": run_id,
                "seed": seed,
                "t": t,
                "delay_setting": delay_setting_name,
                "method": method_name,
                "arrival_batch_size": arrival_batch_size,
                "mean_source_state_distance": mean_source_state_distance,
                "ranking_reversal_rate_at_t": ranking_reversal_rate_at_t,
                "current_state": S_t,
                "optimal_action_current": a_star,
                "arrival_rate_so_far": arrival_rate_t,
                "cumulative_causal_regret": cum_regret,
            }
        )

        step_rows.append(
            {
                "run_id": run_id,
                "seed": seed,
                "t": t,
                "T": T,
                "K": len(A),
                "delay_setting": delay_setting_name,
                "method": method_name,
                "action_selected": a_t,
                "optimal_action_current": a_star,
                "loss_selected_current": loss_t,
                "loss_optimal_current": loss_star,
                "instant_causal_regret": instant_regret,
                "cumulative_causal_regret": cum_regret,
                "delay_tau": d,
                "arrival_t": arrival_t,
                "is_censored": censored,
                "scheduled_count_so_far": scheduled_total,
                "arrived_count_so_far": arrived_total,
                "arrival_rate_so_far": arrival_rate_t,
                "current_state": S_t,
                "epsilon_used": eps,
            }
        )

        delays.append(d)

        env.step(t)

    distance_values = [row["source_state_distance"] for row in arrival_rows]
    if distance_values:
        source_state_distance_mean = sum(distance_values) / len(distance_values)
        source_state_distance_sum = sum(distance_values)
        source_state_distance_p90 = float(np.percentile(distance_values, 90))
    else:
        source_state_distance_mean = "NA"
        source_state_distance_sum = "NA"
        source_state_distance_p90 = "NA"

    ranking_reversals = [row["ranking_reversal"] for row in arrival_rows]
    ranking_reversal_rate = (
        sum(ranking_reversals) / len(ranking_reversals) if ranking_reversals else 0.0
    )

    seed_summary = {
        "run_id": run_id,
        "seed": seed,
        "T": T,
        "K": len(A),
        "delay_setting": delay_setting_name,
        "method": method_name,
        "final_causal_regret": cum_regret,
        "normalized_final_regret": cum_regret / T,
        "auc_causal_regret": sum(regret_list) / T,
        "mean_instant_causal_regret": sum(instant_regrets) / len(instant_regrets),
        "arrival_rate_final": arrival_list[-1] if arrival_list else 0.0,
        "mean_delay": sum(delays) / len(delays) if delays else 0.0,
        "median_delay": float(np.median(delays)) if delays else 0.0,
        "p90_delay": float(np.percentile(delays, 90)) if delays else 0.0,
        "max_delay": max(delays) if delays else 0,
        "censor_rate": sum(1 for row in delay_rows if row["is_censored"]) / T,
        "ranking_reversal_rate": ranking_reversal_rate,
        "source_state_distance_mean": source_state_distance_mean,
        "source_state_distance_sum": source_state_distance_sum,
        "source_state_distance_p90": source_state_distance_p90,
        "gain_vs_naive": None,
        "gain_vs_naive_pct": None,
    }

    return SingleRunResult(
        regret=regret_list,
        arrival_rate=arrival_list,
        step_rows=step_rows,
        delay_rows=delay_rows,
        arrival_rows=arrival_rows,
        diagnostic_rows=diagnostic_rows,
        seed_summary=seed_summary,
    )

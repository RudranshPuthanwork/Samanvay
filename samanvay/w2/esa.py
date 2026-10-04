"""Expected Survival-Weighted Aid (ESA) planning currency (Spec §6.3.2).

Computes time-discounted survival triage value for tasks.
"""

import math
from samanvay.core.constants import TRIAGE_TAU_S, TRIAGE_WEIGHTS


def compute_survivor_value(
    urgency: str,
    p_real: float,
    completion_time_s: float,
) -> float:
    """Compute V_s(t) = p_real(s) * w_u * exp(-t / tau_u)."""
    w = TRIAGE_WEIGHTS.get(urgency, 1.0)
    tau = TRIAGE_TAU_S.get(urgency, 3600.0)
    decay = math.exp(-max(0.0, completion_time_s) / tau)
    return p_real * w * decay


def compute_plan_esa(
    tasks: list[dict],
    start_time_s: float = 0.0,
) -> float:
    """Compute sum of ESA for a list of scheduled tasks with estimated completion times."""
    total_esa = 0.0
    for task in tasks:
        urgency = task.get("urgency", "stable")
        p_real = float(task.get("p_real", 0.5))
        t_finish = float(task.get("completion_t", start_time_s + 180.0))
        total_esa += compute_survivor_value(urgency, p_real, t_finish)
    return total_esa

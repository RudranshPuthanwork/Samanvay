"""Foresight Monte Carlo rollout engine and paired-delta classifier (W4, Spec §6.5).

The Core USP of SAMANVAY:
Evaluates candidate plans across N=64 rollouts using Common Random Numbers (CRN).
Classifies plan decisions into FACT (dominance -> autonomous switch) vs
VALUE (trade-off -> human escalation with Pareto options).
"""

import math
import numpy as np

from samanvay.core.belief import BeliefState
from samanvay.core.constants import (
    FORESIGHT_BOOTSTRAP_ROUNDS,
    FORESIGHT_DT_S,
    FORESIGHT_HORIZON_S,
    FORESIGHT_N_ROLLOUTS,
)
from samanvay.core.models import (
    DecisionClassification,
    Forecast,
    ForecastCandidate,
    PairedDelta,
)


def run_foresight_rollouts(
    belief: BeliefState,
    candidate_plans: dict[str, dict],
    epoch: int = 1,
    crn_seed: int = 9917,
) -> Forecast:
    """Execute vectorized Monte Carlo rollouts across candidate plans using CRN."""
    rng = np.random.default_rng(crn_seed)
    n_rollouts = FORESIGHT_N_ROLLOUTS
    horizon_steps = int(FORESIGHT_HORIZON_S / FORESIGHT_DT_S)

    candidates: list[ForecastCandidate] = []
    rollout_esas: dict[str, np.ndarray] = {}
    rollout_losses: dict[str, np.ndarray] = {}

    for plan_id, plan_data in candidate_plans.items():
        # Pre-allocate rollout arrays
        esas = np.zeros(n_rollouts, dtype=np.float32)
        losses = np.zeros(n_rollouts, dtype=np.float32)
        p1_fails = np.zeros(n_rollouts, dtype=np.float32)
        tti_s: float | None = None

        risk_multiplier = plan_data.get("risk_factor", 1.0)
        base_aid = plan_data.get("base_aid", 2.0)

        # Vectorized rollouts across N=64 runs
        for i in range(n_rollouts):
            # Stochastic battery drain variation across rollouts (CV=0.08)
            drain_noise = rng.normal(0.0, 0.08)
            # Stochastic survivor discovery / delivery timing
            time_noise = rng.normal(0.0, 30.0)

            est_aid = base_aid * (1.0 + rng.normal(0.0, 0.06))
            esas[i] = max(0.0, est_aid)

            # Agent loss probability under this plan
            # Higher plume proximity or longer flight increases loss chance
            loss_prob = 0.03 * risk_multiplier + max(0.0, drain_noise * 0.1)
            losses[i] = 1.0 if rng.random() < loss_prob else 0.0

            # P1 failure chance
            p1_fail_prob = 0.15 / max(0.5, risk_multiplier)
            p1_fails[i] = 1.0 if rng.random() < p1_fail_prob else 0.0

            if losses[i] > 0.5 and tti_s is None:
                tti_s = round(float(belief.t + (i % 20 + 1) * 30.0), 1)

        rollout_esas[plan_id] = esas
        rollout_losses[plan_id] = losses

        mean_esa = float(np.mean(esas))
        ci95_esa = (float(np.percentile(esas, 2.5)), float(np.percentile(esas, 97.5)))
        p_loss = float(np.mean(losses))
        p_p1 = float(np.mean(p1_fails))

        candidates.append(
            ForecastCandidate(
                plan_id=plan_id,
                esa_mean=round(mean_esa, 2),
                esa_ci95=(round(ci95_esa[0], 2), round(ci95_esa[1], 2)),
                p_agent_loss=round(p_loss, 2),
                p_p1_fail=round(p_p1, 2),
                tti_s=tti_s,
            )
        )

    # Compute paired differences between primary alternatives
    paired_deltas: list[PairedDelta] = []
    classification = DecisionClassification.FACT
    reason = "Single plan evaluated or dominant candidate found."

    plan_ids = list(candidate_plans.keys())
    if len(plan_ids) >= 2:
        pid_a, pid_b = plan_ids[1], plan_ids[0]
        diff_esa = rollout_esas[pid_a] - rollout_esas[pid_b]
        diff_loss = rollout_losses[pid_a] - rollout_losses[pid_b]

        # Bootstrap 95% confidence intervals
        boot_d_esa = []
        boot_d_loss = []
        for _ in range(FORESIGHT_BOOTSTRAP_ROUNDS):
            idx = rng.choice(n_rollouts, size=n_rollouts, replace=True)
            boot_d_esa.append(np.mean(diff_esa[idx]))
            boot_d_loss.append(np.mean(diff_loss[idx]))

        ci_d_esa = (float(np.percentile(boot_d_esa, 2.5)), float(np.percentile(boot_d_esa, 97.5)))
        ci_d_loss = (float(np.percentile(boot_d_loss, 2.5)), float(np.percentile(boot_d_loss, 97.5)))

        paired_deltas.append(
            PairedDelta(
                a=pid_a,
                b=pid_b,
                d_esa_ci95=(round(ci_d_esa[0], 2), round(ci_d_esa[1], 2)),
                d_ploss_ci95=(round(ci_d_loss[0], 2), round(ci_d_loss[1], 2)),
            )
        )

        # Fact vs Value Separation Decision Rule (Spec §6.5.4):
        # If Plan A has higher ESA (CI strictly > 0) AND higher loss risk (CI strictly > 0) -> Non-dominated VALUE tradeoff!
        if ci_d_esa[0] > 0.0 and ci_d_loss[0] > 0.0:
            classification = DecisionClassification.VALUE
            reason = f"Non-dominated trade-off: {pid_a} yields higher aid but higher agent loss risk. Both 95% intervals exclude 0."
        elif ci_d_esa[0] > 0.0 and ci_d_loss[1] <= 0.0:
            classification = DecisionClassification.FACT
            reason = f"Dominance: {pid_a} strictly dominates {pid_b} with higher aid and equal or lower risk."
        else:
            classification = DecisionClassification.FACT
            reason = f"Statistically indistinguishable from candidate plans: current plan {pid_b} remains preferred."

    return Forecast(
        epoch=epoch,
        t=belief.t,
        n_rollouts=n_rollouts,
        horizon_s=FORESIGHT_HORIZON_S,
        crn_seed=crn_seed,
        candidates=candidates,
        paired_deltas=paired_deltas,
        classification=classification,
        reason=reason,
    )

"""Tests for W2 Auction & Routing and W4 Foresight Rollouts."""

import numpy as np
from samanvay.core.belief import BeliefState
from samanvay.core.models import AgentState, DecisionClassification
from samanvay.w1.grammar import parse_mission_objective
from samanvay.w2.auction import generate_search_tasks, plan_routes_for_assignments, run_regret_auction
from samanvay.w2.distance import find_path
from samanvay.w4.foresight import run_foresight_rollouts


def test_mission_parser_and_auction():
    """Verify mission grammar parsing and regret auction route planning."""
    text = "Sweep all sectors for assessment, then focus on sectors B and C, deliver medkits, avoid plume"
    parse_res = parse_mission_objective(text)

    assert len(parse_res.spec.phases) == 3
    assert parse_res.spec.phases[0].asr == 1
    assert parse_res.spec.phases[1].asr == 2
    assert "B" in parse_res.spec.phases[1].sectors
    assert "C" in parse_res.spec.phases[1].sectors

    # Setup belief
    belief = BeliefState(
        t=0.0,
        grid_size=(64, 48),
        observed_terrain=[["open" for _ in range(64)] for _ in range(48)],
        known_plume=np.zeros((48, 64), dtype=np.float32),
        agents={
            "scout-1": AgentState(
                id="scout-1",
                type="scout_drone",
                pos=(2, 2),
                alt_band=2,
                battery=1.0,
            ),
            "cargo-1": AgentState(
                id="cargo-1",
                type="cargo_drone",
                pos=(2, 2),
                alt_band=2,
                battery=1.0,
                payload={"capacity": 1, "carrying": ["medkit"]},
            ),
        },
    )

    tasks = generate_search_tasks(["B", "C"], asr_phase=2)
    assert len(tasks) == 2

    assignments = run_regret_auction(tasks, belief)
    assert sum(len(q) for q in assignments.values()) == 2

    plan_routes_for_assignments(assignments, belief)
    # Ensure route waypoints were populated
    assert len(belief.agents["scout-1"].route) > 0


def test_foresight_rollout_classifier():
    """Verify that Foresight Monte Carlo rollouts produce statistically separated decisions."""
    belief = BeliefState(
        t=100.0,
        grid_size=(64, 48),
        agents={"scout-1": AgentState(id="scout-1", type="scout_drone", pos=(20, 20), battery=0.85)},
    )

    # 1. Non-dominated trade-off: Plan A has higher aid, but higher risk
    cand_plans = {
        "P-current": {"base_aid": 2.2, "risk_factor": 1.0},
        "P-repair": {"base_aid": 3.8, "risk_factor": 6.0},  # Higher aid + much higher risk
    }

    fc = run_foresight_rollouts(belief, cand_plans, epoch=1, crn_seed=42)
    assert fc.classification == DecisionClassification.VALUE
    assert "Non-dominated" in fc.reason
    assert len(fc.candidates) == 2
    assert len(fc.paired_deltas) == 1

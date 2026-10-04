"""Hypothesis property tests for Regret SSI auction feasibility (Spec §6.3.3)."""

from hypothesis import given, settings, strategies as st
from samanvay.core.belief import BeliefState
from samanvay.core.constants import GRID_HEIGHT, GRID_WIDTH
from samanvay.core.models import AgentState, PriorityClass, Task, TaskStatus, TaskType, ValueModel
from samanvay.core.registry import STANDARD_AGENT_TYPES
from samanvay.w2.auction import run_regret_auction


@settings(max_examples=40, deadline=None)
@given(
    n_tasks=st.integers(min_value=1, max_value=8),
    has_cargo=st.booleans(),
    has_rover=st.booleans(),
)
def test_hypothesis_auction_feasibility(n_tasks, has_cargo, has_rover):
    """Verify that all assignments made by the auction satisfy capability constraints."""
    agents = {
        "scout-1": AgentState(id="scout-1", type="scout_drone", pos=(2, 2), battery=0.9),
        "scout-2": AgentState(id="scout-2", type="scout_drone", pos=(2, 2), battery=0.9),
    }
    if has_cargo:
        agents["cargo-1"] = AgentState(
            id="cargo-1", type="cargo_drone", pos=(2, 2), battery=0.9, payload={"capacity": 1, "carrying": ["medkit"]}
        )
    if has_rover:
        agents["rover-1"] = AgentState(
            id="rover-1", type="ground_rover", pos=(2, 2), battery=0.9, payload={"capacity": 4, "carrying": ["medkit"]}
        )

    belief = BeliefState(
        t=0.0,
        grid_size=(GRID_WIDTH, GRID_HEIGHT),
        agents=agents,
    )

    tasks: list[Task] = []
    for i in range(n_tasks):
        # Even tasks are search, odd tasks are deliver
        t_type = TaskType.SEARCH if (i % 2 == 0) else TaskType.DELIVER
        requires = ["search_sensor"] if t_type == TaskType.SEARCH else ["cargo_bay"]
        tasks.append(
            Task(
                id=f"task-{i}",
                type=t_type,
                priority_class=PriorityClass.P2,
                location=(10 + i * 2, 10 + i * 2),
                requires=requires,
                value_model=ValueModel(urgency="critical", p_real=0.8),
                status=TaskStatus.PENDING,
            )
        )

    assignments = run_regret_auction(tasks, belief)

    # Invariant: Every assigned agent possesses the required capability for all its assigned tasks
    for aid, assigned_tasks in assignments.items():
        agent = belief.agents[aid]
        spec = STANDARD_AGENT_TYPES[agent.type]
        for t in assigned_tasks:
            for req in t.requires:
                assert req in spec.capabilities, f"Agent {aid} assigned {t.id} without capability {req}"

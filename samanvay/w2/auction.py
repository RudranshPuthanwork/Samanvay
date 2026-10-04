"""Regret-based Sequential Single-Item (SSI) task auction (Spec §6.3.3).

Assigns search sectors, verification tasks, and rescue deliveries to agents
maximizing Expected Survival-Weighted Aid (ESA) while respecting traversability
and payload constraints.
"""

import math
from typing import Any
from samanvay.core.belief import BeliefState
from samanvay.core.models import PriorityClass, Task, TaskStatus, TaskType, ValueModel
from samanvay.core.registry import STANDARD_AGENT_TYPES
from samanvay.w2.distance import find_path
from samanvay.w2.esa import compute_survivor_value


# 4 Quad Sectors
SECTOR_BOUNDS: dict[str, tuple[int, int, int, int]] = {
    # (min_x, max_x, min_y, max_y)
    "A": (0, 31, 0, 23),    # NW
    "B": (32, 63, 0, 23),   # NE
    "C": (0, 31, 24, 47),   # SW
    "D": (32, 63, 24, 47),  # SE
}


def generate_search_tasks(
    sectors: list[str],
    asr_phase: int = 1,
) -> list[Task]:
    """Generate SEARCH tasks for the requested sectors."""
    tasks: list[Task] = []
    target_sectors = sectors if sectors else ["A", "B", "C", "D"]

    for sec in target_sectors:
        bounds = SECTOR_BOUNDS.get(sec, (0, 31, 0, 23))
        # Center of sector
        cx = (bounds[0] + bounds[1]) // 2
        cy = (bounds[2] + bounds[3]) // 2
        tid = f"search-{sec}-phase{asr_phase}"
        tasks.append(
            Task(
                id=tid,
                type=TaskType.SEARCH,
                priority_class=PriorityClass.P3,
                asr_phase=asr_phase,
                location=(cx, cy),
                requires=["search_sensor"],
                value_model=ValueModel(urgency="stable", p_real=0.4),
                status=TaskStatus.PENDING,
            )
        )
    return tasks


def run_regret_auction(
    tasks: list[Task],
    belief: BeliefState,
) -> dict[str, list[Task]]:
    """Execute Regret-based SSI auction to assign unassigned tasks to agents.

    Returns:
        Mapping of agent_id -> list of newly assigned tasks in order.
    """
    unassigned = [t for t in tasks if t.status == TaskStatus.PENDING and not t.assigned_to]
    assigned_queues: dict[str, list[Task]] = {aid: [] for aid in belief.agents}

    # Available agents and specs
    active_agents = {
        aid: st for aid, st in belief.agents.items()
        if st.status != "lost" and st.status != "failed" and st.battery > 0.15
    }

    if not active_agents or not unassigned:
        return assigned_queues

    while unassigned:
        task_bids: list[dict[str, Any]] = []

        for task in unassigned:
            bids_for_task: list[tuple[float, str]] = []

            for aid, st in active_agents.items():
                spec = STANDARD_AGENT_TYPES.get(st.type)
                if not spec:
                    continue

                # Capability check
                reqs = set(task.requires)
                if not reqs.issubset(spec.capabilities):
                    continue

                # Payload check for delivery
                if task.type == TaskType.DELIVER:
                    if spec.payload_capacity <= 0:
                        continue

                # Compute insertion distance from current pos (or end of assigned queue)
                last_pos = assigned_queues[aid][-1].location if assigned_queues[aid] else st.pos
                dist = math.hypot(task.location[0] - last_pos[0], task.location[1] - last_pos[1])
                duration_est = (dist * 10.0) / max(0.1, spec.speed_mps)

                # Estimated completion time
                t_comp = belief.t + duration_est
                val = compute_survivor_value(
                    urgency=task.value_model.urgency,
                    p_real=task.value_model.p_real,
                    completion_time_s=t_comp,
                )

                # Net marginal bid (value / cost)
                bid_score = val / (1.0 + duration_est * 0.01)
                bids_for_task.append((bid_score, aid))

            if not bids_for_task:
                continue

            # Sort bids descending
            bids_for_task.sort(key=lambda x: x[0], reverse=True)
            best_bid, best_aid = bids_for_task[0]
            second_best_bid = bids_for_task[1][0] if len(bids_for_task) > 1 else 0.0
            regret = best_bid - second_best_bid

            task_bids.append({
                "task": task,
                "best_aid": best_aid,
                "best_bid": best_bid,
                "regret": regret,
            })

        if not task_bids:
            break

        # Pick task with highest regret (or highest bid)
        task_bids.sort(key=lambda x: (x["regret"], x["best_bid"]), reverse=True)
        winner = task_bids[0]
        won_task = winner["task"]
        won_aid = winner["best_aid"]

        # Award task
        assigned_task = won_task.model_copy(
            update={"status": TaskStatus.ASSIGNED, "assigned_to": won_aid}
        )
        assigned_queues[won_aid].append(assigned_task)
        unassigned.remove(won_task)

    return assigned_queues


def plan_routes_for_assignments(
    assignments: dict[str, list[Task]],
    belief: BeliefState,
) -> None:
    """Generate waypoints for assigned tasks using A* pathfinding."""
    for aid, new_tasks in assignments.items():
        if not new_tasks:
            continue

        agent_st = belief.agents.get(aid)
        if not agent_st:
            continue

        spec = STANDARD_AGENT_TYPES.get(agent_st.type)
        if not spec:
            continue

        curr_pos = agent_st.pos
        full_route: list[tuple[int, int]] = list(agent_st.route)

        for task in new_tasks:
            goal_pos = task.location
            start_for_segment = full_route[-1] if full_route else curr_pos
            is_air = "move_air" in spec.capabilities

            # Pathfind
            path = find_path(
                start=start_for_segment,
                goal=goal_pos,
                traversable_terrains=spec.traversable,
                terrain_grid=belief.observed_terrain,
                plume_grid=belief.known_plume.tolist(),
                is_air_agent=is_air,
            )
            if path:
                # Append waypoints (skipping duplicate first point)
                pts = path[1:] if full_route else path
                full_route.extend(pts)
                belief.tasks[task.id] = task

        # Update agent state
        new_queue = list(agent_st.queue) + [t.id for t in new_tasks]
        belief.agents[aid] = agent_st.model_copy(
            update={
                "route": full_route,
                "queue": new_queue,
                "status": "executing" if full_route else agent_st.status,
            }
        )

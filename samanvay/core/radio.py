"""Radio link and multihop mesh network connectivity model (Spec §6.4.1).

Models BFS reachability from the base station through mobile mesh relays.
"""

import math
from collections import deque
from samanvay.core.constants import BASE_COORDINATES, BASE_RADIO_RANGE_M, CELL_METERS
from samanvay.core.models import AgentState


def compute_distance_m(cell_a: tuple[float, float], cell_b: tuple[float, float]) -> float:
    """Compute Euclidean distance in meters between two grid cells."""
    dx = (cell_a[0] - cell_b[0]) * CELL_METERS
    dy = (cell_a[1] - cell_b[1]) * CELL_METERS
    return math.hypot(dx, dy)


def compute_radio_mesh(
    agents: dict[str, AgentState],
    agent_ranges: dict[str, float],
    base_pos: tuple[float, float] = BASE_COORDINATES,
    base_range_m: float = BASE_RADIO_RANGE_M,
) -> tuple[set[str], list[tuple[str, str]]]:
    """Calculate multihop network connectivity from base station using BFS.

    Returns:
        (connected_agent_ids, active_edges)
    """
    # Nodes in graph: "base" + all agent ids
    adj: dict[str, list[str]] = {"base": []}
    for aid in agents:
        adj[aid] = []

    active_edges: list[tuple[str, str]] = []

    # 1. Base to agent edges
    for aid, state in agents.items():
        dist = compute_distance_m(base_pos, (float(state.pos[0]), float(state.pos[1])))
        r_eff = min(base_range_m, agent_ranges.get(aid, 300.0))
        if dist <= r_eff:
            adj["base"].append(aid)
            adj[aid].append("base")
            active_edges.append(("base", aid))

    # 2. Agent to agent edges
    agent_keys = list(agents.keys())
    for i in range(len(agent_keys)):
        aid1 = agent_keys[i]
        st1 = agents[aid1]
        r1 = agent_ranges.get(aid1, 300.0)
        for j in range(i + 1, len(agent_keys)):
            aid2 = agent_keys[j]
            st2 = agents[aid2]
            r2 = agent_ranges.get(aid2, 300.0)
            r_eff = min(r1, r2)
            dist = compute_distance_m((float(st1.pos[0]), float(st1.pos[1])), (float(st2.pos[0]), float(st2.pos[1])))
            if dist <= r_eff:
                adj[aid1].append(aid2)
                adj[aid2].append(aid1)
                active_edges.append((aid1, aid2))

    # 3. BFS from "base"
    visited: set[str] = set()
    queue: deque[str] = deque(["base"])
    visited.add("base")

    while queue:
        curr = queue.popleft()
        for neighbor in adj.get(curr, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    connected_agents = visited - {"base"}
    return connected_agents, active_edges

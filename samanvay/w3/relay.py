"""Relay drone placement optimizer (Spec §6.4.4)."""

import math
from samanvay.core.constants import BASE_COORDINATES
from samanvay.core.models import AgentState


def compute_optimal_relay_position(
    agents: dict[str, AgentState],
    base_pos: tuple[int, int] = BASE_COORDINATES,
) -> tuple[int, int]:
    """Find midpoint position for Relay-1 to bridge Base station with distant agents."""
    distant_agents = [
        st for aid, st in agents.items()
        if aid != "relay-1" and math.hypot(st.pos[0] - base_pos[0], st.pos[1] - base_pos[1]) * 10.0 > 250.0
    ]

    if not distant_agents:
        # Hover near center-north if all agents are near
        return (24, 18)

    # Average position of distant agents
    avg_x = sum(st.pos[0] for st in distant_agents) / len(distant_agents)
    avg_y = sum(st.pos[1] for st in distant_agents) / len(distant_agents)

    # Relay midpoint between base and average distant position
    relay_x = int(round((base_pos[0] + avg_x) / 2.0))
    relay_y = int(round((base_pos[1] + avg_y) / 2.0))
    return (relay_x, relay_y)

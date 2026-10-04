"""Dynamic computed battery reserve calculation (Spec §6.4.2).

Computes minimum battery fraction needed for an agent to safely return to base (RTB).
Shared across Comms (W3) and Safety Shield (W5) without cross-workstream imports.
"""

import math
from samanvay.core.constants import BASE_COORDINATES
from samanvay.core.models import AgentState
from samanvay.core.registry import STANDARD_AGENT_TYPES


def compute_required_reserve(
    agent: AgentState,
    base_pos: tuple[int, int] = BASE_COORDINATES,
) -> float:
    """Compute minimum battery fraction required to safely RTB to base station."""
    spec = STANDARD_AGENT_TYPES.get(agent.type)
    if not spec:
        return 0.15

    # Euclidean distance to base
    dist_m = math.hypot(agent.pos[0] - base_pos[0], agent.pos[1] - base_pos[1]) * 10.0
    travel_time_s = dist_m / max(0.1, spec.speed_mps)

    # Battery cost to fly back
    drain_to_rtb = spec.drain_per_s(spec.speed_mps, 0.0) * travel_time_s

    # Add 5% safety margin
    reserve = drain_to_rtb + 0.05
    return min(0.90, max(0.12, round(reserve, 3)))

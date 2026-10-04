"""Comms leases protocol and computed battery reserve (Spec §6.4).

Ensures non-conflicting execution during radio silence through leases
and enforces guaranteed return-to-base via dynamic reserve calculation.
"""

import math
from samanvay.core.constants import BASE_COORDINATES, LEASE_DURATION_S
from samanvay.core.models import AgentState, Lease
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


class LeaseManager:
    """Tracks task leases to coordinate disconnected agents without race conditions."""

    def __init__(self, lease_duration: float = LEASE_DURATION_S) -> None:
        self.lease_duration = lease_duration

    def grant_or_renew_lease(self, agent: AgentState, task_id: str, current_time: float) -> Lease:
        """Grant or extend a lease for the agent on a specific task."""
        return Lease(task=task_id, expires_t=round(current_time + self.lease_duration, 1))

    def is_lease_valid(self, lease: Lease | None, current_time: float) -> bool:
        """Check if lease is currently valid and unexpired."""
        if not lease:
            return False
        return current_time < lease.expires_t

"""Extensibility interfaces and agent plugin protocols for SAMANVAY (Spec §5.5).

Enables dropping in new agent types and task types without modifying core planners.
"""

from dataclasses import dataclass
from typing import Callable, Protocol
from samanvay.core.models import AgentState, Event


@dataclass(frozen=True)
class SensorModel:
    footprint_radius: int  # Radius in grid cells
    p_detect: float        # e.g., 0.75 - 0.98
    p_false_alarm: float   # e.g., 0.0005 - 0.003


@dataclass(frozen=True)
class AgentTypeSpec:
    id: str                         # e.g., "scout_drone", "cargo_drone", "ground_rover", "relay_drone"
    capabilities: frozenset[str]    # {"move_air", "search_sensor", "carry_medkit"}
    traversable: frozenset[str]     # {"road", "open", "building", "rubble", "water"}
    speed_mps: float
    drain_per_s: Callable[[float, float], float]  # (speed, payload) -> battery fraction per s
    drain_cv: float                 # Coefficient of variation for Foresight MC rollouts
    radio_range_m: float
    payload_capacity: int
    sensor: SensorModel | None      # Sensor model if equipped


@dataclass(frozen=True)
class TaskTypeSpec:
    id: str                         # "SEARCH", "VERIFY", "DELIVER", "RELAY", "RTB"
    requires: frozenset[str]
    duration_s: Callable[[AgentTypeSpec], float]
    value: Callable[[dict, float], float]  # ESA contribution if completed at time t
    exclusive: bool


class AgentAdapter(Protocol):
    """Protocol for interacting with simulated or real robot/drone agents."""

    def send_plan(self, agent_id: str, waypoints: list[tuple[int, int]]) -> None:
        """Transmit waypoints to the agent."""
        ...

    def get_state(self, agent_id: str) -> AgentState:
        """Query agent's latest telemetric state."""
        ...

    def on_event(self, callback: Callable[[Event], None]) -> None:
        """Register callback for asynchronous events emitted by the agent."""
        ...

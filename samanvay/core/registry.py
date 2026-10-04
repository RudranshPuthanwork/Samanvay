"""Agent and task type registry implementing standard SAMANVAY assets (Spec §6.1.2).
"""

from typing import Final
from samanvay.core.extensibility import AgentTypeSpec, SensorModel, TaskTypeSpec


def _scout_drain(speed: float, payload: float) -> float:
    # 25 min endurance -> 1 / 1500s ≈ 0.00067/s
    return 0.00067 * (1.0 + 0.05 * (speed / 8.0))


def _cargo_drain(speed: float, payload: float) -> float:
    # 18 min loaded (0.00092/s), 28 min empty (0.00059/s)
    base = 0.00059 if payload == 0 else 0.00092
    return base * (1.0 + 0.05 * (speed / 5.0))


def _rover_drain(speed: float, payload: float) -> float:
    # 120 min endurance -> 1 / 7200s ≈ 0.000138/s
    return 0.00014 * (1.0 + 0.02 * payload)


def _relay_drain(speed: float, payload: float) -> float:
    # 40 min endurance -> 1 / 2400s ≈ 0.000416/s
    return 0.00042 * (1.0 + 0.03 * (speed / 6.0))


STANDARD_AGENT_TYPES: Final[dict[str, AgentTypeSpec]] = {
    "scout_drone": AgentTypeSpec(
        id="scout_drone",
        capabilities=frozenset({"move_air", "search_sensor", "high_band", "low_band"}),
        traversable=frozenset({"road", "open", "building", "rubble", "water", "base"}),
        speed_mps=8.0,
        drain_per_s=_scout_drain,
        drain_cv=0.08,
        radio_range_m=300.0,
        payload_capacity=0,
        sensor=SensorModel(footprint_radius=2, p_detect=0.75, p_false_alarm=0.003),
    ),
    "cargo_drone": AgentTypeSpec(
        id="cargo_drone",
        capabilities=frozenset({"move_air", "carry_payload", "deliver_medkit"}),
        traversable=frozenset({"road", "open", "building", "rubble", "water", "base"}),
        speed_mps=5.0,
        drain_per_s=_cargo_drain,
        drain_cv=0.10,
        radio_range_m=300.0,
        payload_capacity=1,
        sensor=None,
    ),
    "ground_rover": AgentTypeSpec(
        id="ground_rover",
        capabilities=frozenset({"move_ground", "search_sensor", "carry_payload", "verify_survivor", "deliver_medkit"}),
        traversable=frozenset({"road", "open", "base"}),  # Cannot cross rubble or water
        speed_mps=1.5,
        drain_per_s=_rover_drain,
        drain_cv=0.05,
        radio_range_m=150.0,
        payload_capacity=4,
        sensor=SensorModel(footprint_radius=1, p_detect=0.98, p_false_alarm=0.0005),
    ),
    "relay_drone": AgentTypeSpec(
        id="relay_drone",
        capabilities=frozenset({"move_air", "radio_relay", "hover"}),
        traversable=frozenset({"road", "open", "building", "rubble", "water", "base"}),
        speed_mps=6.0,
        drain_per_s=_relay_drain,
        drain_cv=0.06,
        radio_range_m=600.0,
        payload_capacity=0,
        sensor=None,
    ),
}

"""Ground truth world state for SAMANVAY simulation and evaluation (Spec §5.3.1, §6.1).

CRITICAL FIREWALL RULE (§5.4):
This module represents hidden ground truth and MUST ONLY be imported by
`samanvay.sim` and `samanvay.eval`. Planning, Foresight, Comms, and UI modules
must NEVER import this module.
"""

from dataclasses import dataclass, field
import numpy as np


@dataclass
class SurvivorTruth:
    id: str
    cell: tuple[int, int]
    urgency: str  # "critical", "serious", "stable"
    discovered: bool = False
    aided: bool = False
    t_discovered: float | None = None
    t_aided: float | None = None


@dataclass
class AgentTruth:
    id: str
    type_id: str
    pos: tuple[float, float]
    alt_band: int
    battery: float  # 0.0 to 1.0
    drain_rate: float
    connected: bool = True
    active: bool = True
    carrying: list[str] = field(default_factory=list)
    comms_denied_until: float = 0.0


@dataclass
class TruthWorld:
    """Complete ground-truth state of the disaster environment."""
    scenario_id: str
    seed: int
    grid_size: tuple[int, int] = (64, 48)
    cell_m: float = 10.0
    t: float = 0.0

    # Terrains: "road", "open", "building", "rubble", "water", "base"
    base_terrain: list[list[str]] = field(default_factory=list)
    realized_terrain: list[list[str]] = field(default_factory=list)

    # Earthquake & Damage
    epicentre: tuple[int, int] = (10, 40)
    intensity_field: np.ndarray = field(default_factory=lambda: np.zeros((48, 64), dtype=np.float32))
    collapsed_buildings: set[tuple[int, int]] = field(default_factory=set)
    rubble_cells: set[tuple[int, int]] = field(default_factory=set)

    # Chemical Plume
    plume_source: tuple[int, int] = (30, 20)
    wind_deg: float = 225.0
    wind_mps: float = 4.0
    plume_grid: np.ndarray = field(default_factory=lambda: np.zeros((48, 64), dtype=np.float32))

    # Agents & Survivors
    survivors: dict[str, SurvivorTruth] = field(default_factory=dict)
    agents: dict[str, AgentTruth] = field(default_factory=dict)

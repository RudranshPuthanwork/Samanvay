"""Scenario generator (W0 Scenario Lab, Spec §6.1).

Produces reproducible disaster scenarios with exact ground truth (TruthWorld)
and ScenarioManifest for families F1 (urban quake) and F4 (night, degraded comms).
"""

import math
import numpy as np

from samanvay.core.constants import BASE_COORDINATES, BASE_STAGING_PADS, GRID_HEIGHT, GRID_WIDTH
from samanvay.core.models import (
    MapManifest,
    PlumeManifest,
    QuakeManifest,
    ScenarioManifest,
    ScheduledEventManifest,
    SurvivorManifest,
    EventType,
)
from samanvay.core.truth import AgentTruth, SurvivorTruth, TruthWorld


def generate_scenario(
    family: str = "F1",
    seed: int = 42,
    scenario_id: str | None = None,
) -> tuple[ScenarioManifest, TruthWorld]:
    """Generate synthetic scenario and exact ground-truth world state."""
    rng = np.random.default_rng(seed)
    scen_id = scenario_id or f"{family}_s{seed:04d}"

    # 1. Base terrain map (64 wide x 48 high)
    # Terrain classes: "road", "open", "building", "rubble", "water", "base"
    base_terrain: list[list[str]] = [["open" for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]

    # Roads on a regular grid: every 8 cells
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if x % 8 == 0 or y % 8 == 0:
                base_terrain[y][x] = "road"

    # Fill some blocks with buildings (avoiding perimeter and base)
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if base_terrain[y][x] == "open":
                bx, by = x % 8, y % 8
                # Center of block is building
                if 2 <= bx <= 5 and 2 <= by <= 5:
                    if not (x < 8 and y < 8):  # Leave room around base
                        base_terrain[y][x] = "building"

    # Base station at (2, 2)
    bx, by = BASE_COORDINATES
    base_terrain[by][bx] = "base"

    # Copy to realized terrain
    realized_terrain = [row[:] for row in base_terrain]

    # 2. Quake intensity field
    epicentre = (12, 38)
    decay_lambda = 28.0
    intensity_field = np.zeros((GRID_HEIGHT, GRID_WIDTH), dtype=np.float32)

    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            d = math.hypot(x - epicentre[0], y - epicentre[1])
            noise = rng.normal(0.0, 0.05)
            intensity = 1.0 * math.exp(-d / decay_lambda) + noise
            intensity_field[y, x] = max(0.0, float(intensity))

    # 3. Building collapse and road rubble
    collapsed_buildings: set[tuple[int, int]] = set()
    rubble_cells: set[tuple[int, int]] = set()

    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if base_terrain[y][x] == "building":
                # Collapse probability sigmoid on intensity
                p_collapse = 1.0 / (1.0 + math.exp(-10.0 * (intensity_field[y, x] - 0.45)))
                if rng.random() < p_collapse:
                    collapsed_buildings.add((x, y))
                    realized_terrain[y][x] = "rubble"
                    # 50% chance to spill rubble to adjacent road cells
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                            if base_terrain[ny][nx] == "road" and (nx, ny) != BASE_COORDINATES:
                                if rng.random() < 0.5:
                                    rubble_cells.add((nx, ny))
                                    realized_terrain[ny][nx] = "rubble"

    # 4. Survivors (8 to 12 survivors)
    n_survivors = int(np.clip(rng.poisson(8), 5, 12))
    candidate_cells: list[tuple[int, int]] = []
    weights: list[float] = []

    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if (x, y) == BASE_COORDINATES:
                continue
            if (x, y) in collapsed_buildings:
                candidate_cells.append((x, y))
                weights.append(5.0)
            elif (x, y) in rubble_cells:
                candidate_cells.append((x, y))
                weights.append(3.0)
            elif base_terrain[y][x] == "building":
                candidate_cells.append((x, y))
                weights.append(1.0)
            elif base_terrain[y][x] == "open":
                candidate_cells.append((x, y))
                weights.append(0.2)

    total_w = sum(weights)
    probs = [w / total_w for w in weights]
    chosen_indices = rng.choice(len(candidate_cells), size=n_survivors, replace=False, p=probs)

    survivor_manifests: list[SurvivorManifest] = []
    survivor_truth: dict[str, SurvivorTruth] = {}

    urgency_choices = ["critical", "serious", "stable"]
    urgency_weights = [0.2, 0.5, 0.3]

    for idx, cand_idx in enumerate(chosen_indices):
        s_id = f"S{idx + 1}"
        s_cell = candidate_cells[cand_idx]
        urgency = rng.choice(urgency_choices, p=urgency_weights)
        survivor_manifests.append(
            SurvivorManifest(id=s_id, cell=s_cell, urgency=urgency)
        )
        survivor_truth[s_id] = SurvivorTruth(
            id=s_id, cell=s_cell, urgency=urgency, discovered=False, aided=False
        )

    # 5. Plume configuration
    plume_source = (32, 22)
    wind_deg = 225.0  # SW wind
    wind_mps = 4.0
    plume_grid = np.zeros((GRID_HEIGHT, GRID_WIDTH), dtype=np.float32)
    # Seed plume source
    plume_grid[plume_source[1], plume_source[0]] = 0.85

    # 6. Scheduled Events (aftershock at t=300s, wind shift at t=450s)
    scheduled_events = [
        ScheduledEventManifest(
            t=300.0,
            type=EventType.AFTERSHOCK,
            cells=[(24, 32), (25, 32), (24, 33)],
            params={"additional_rubble": True},
        ),
        ScheduledEventManifest(
            t=450.0,
            type=EventType.WEATHER_CHANGE,
            cells=[],
            params={"wind_deg": 270.0, "wind_mps": 6.5},
        ),
    ]

    # 7. Agent Truth
    agent_truth: dict[str, AgentTruth] = {
        "scout-1": AgentTruth(
            id="scout-1",
            type_id="scout_drone",
            pos=BASE_STAGING_PADS.get("scout-1", (1.0, 2.0)),
            alt_band=2,
            battery=1.0,
            drain_rate=0.00067,
        ),
        "scout-2": AgentTruth(
            id="scout-2",
            type_id="scout_drone",
            pos=BASE_STAGING_PADS.get("scout-2", (2.0, 1.0)),
            alt_band=1,
            battery=1.0,
            drain_rate=0.00067,
        ),
        "cargo-1": AgentTruth(
            id="cargo-1",
            type_id="cargo_drone",
            pos=BASE_STAGING_PADS.get("cargo-1", (2.0, 3.0)),
            alt_band=2,
            battery=1.0,
            drain_rate=0.00059,
            carrying=["medkit"],
        ),
        "rover-1": AgentTruth(
            id="rover-1",
            type_id="ground_rover",
            pos=BASE_STAGING_PADS.get("rover-1", (3.0, 2.0)),
            alt_band=0,
            battery=1.0,
            drain_rate=0.00014,
            carrying=["medkit", "medkit", "medkit", "medkit"],
        ),
        "relay-1": AgentTruth(
            id="relay-1",
            type_id="relay_drone",
            pos=BASE_STAGING_PADS.get("relay-1", (3.0, 3.0)),
            alt_band=3,
            battery=1.0,
            drain_rate=0.00042,
        ),
    }

    manifest = ScenarioManifest(
        scenario_id=scen_id,
        family=family,  # type: ignore[arg-type]
        seed=seed,
        map=MapManifest(source="synthetic"),
        quake=QuakeManifest(epicentre_cell=epicentre, intensity_decay_cells=decay_lambda),
        survivors=survivor_manifests,
        plume=PlumeManifest(source_cell=plume_source, wind_deg=wind_deg, wind_mps=wind_mps),
        scheduled_events=scheduled_events,
        agents=list(agent_truth.keys()),
    )

    truth_world = TruthWorld(
        scenario_id=scen_id,
        seed=seed,
        base_terrain=base_terrain,
        realized_terrain=realized_terrain,
        epicentre=epicentre,
        intensity_field=intensity_field,
        collapsed_buildings=collapsed_buildings,
        rubble_cells=rubble_cells,
        plume_source=plume_source,
        wind_deg=wind_deg,
        wind_mps=wind_mps,
        plume_grid=plume_grid,
        survivors=survivor_truth,
        agents=agent_truth,
    )

    return manifest, truth_world

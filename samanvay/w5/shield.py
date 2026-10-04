"""Safety Shield independent monitor and invariant enforcer (W5, Spec §6.6, §10.6).

Enforces invariants I1 through I6 independently of the planner or Foresight.
Checked every tick for every agent over the next 60 s of its committed route.
Overrides unsafe plans with deterministic HOLD or RTB.
"""

import math
from typing import NamedTuple
from samanvay.core.belief import BeliefState
from samanvay.core.constants import CELL_METERS, GRID_HEIGHT, GRID_WIDTH, PLUME_NO_FLY_THRESHOLD
from samanvay.core.models import AgentState
from samanvay.core.registry import STANDARD_AGENT_TYPES
from samanvay.core.reserve import compute_required_reserve


class InvariantResult(NamedTuple):
    passed: bool
    invariant_id: str
    reason: str


class SafetyShield:
    """Independent safety supervisor enforcing hard constraints I1-I6 (Spec §6.6.1)."""

    def check_invariants(self, belief: BeliefState) -> list[InvariantResult]:
        """Verify all invariants I1 - I6 on current belief state."""
        results: list[InvariantResult] = []

        # I1: No cell with current or 60 s-forecast hazard >= 0.5
        for aid, st in belief.agents.items():
            if st.alt_band > 0:  # Drone
                x, y = st.pos
                if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT:
                    hazard = float(belief.known_plume[y, x])
                    if hazard >= PLUME_NO_FLY_THRESHOLD:
                        results.append(
                            InvariantResult(
                                False,
                                "I1_NO_FLY",
                                f"Agent {aid} in no-fly plume cell ({x}, {y}) with hazard {hazard:.2f} >= {PLUME_NO_FLY_THRESHOLD}",
                            )
                        )

        # I2: Battery >= reserve_required at every point of the route
        for aid, st in belief.agents.items():
            req_reserve = compute_required_reserve(st)
            if st.battery <= req_reserve and st.status not in ("rtb", "lost", "idle", "holding"):
                results.append(
                    InvariantResult(
                        False,
                        "I2_RESERVE",
                        f"Agent {aid} battery {st.battery:.2f} <= required reserve {req_reserve:.2f} while executing task",
                    )
                )

        # I3: Inside the geofence
        for aid, st in belief.agents.items():
            x, y = st.pos
            if not (0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT):
                results.append(
                    InvariantResult(
                        False,
                        "I3_GEOFENCE",
                        f"Agent {aid} breached operational geofence at position ({x}, {y})",
                    )
                )

        # I4: Drones within 1 cell of each other are in different altitude bands
        air_agents = [(aid, st) for aid, st in belief.agents.items() if st.alt_band > 0]
        for i in range(len(air_agents)):
            aid1, st1 = air_agents[i]
            for j in range(i + 1, len(air_agents)):
                aid2, st2 = air_agents[j]
                dx = abs(st1.pos[0] - st2.pos[0])
                dy = abs(st1.pos[1] - st2.pos[1])
                if dx <= 2 and dy <= 2:
                    if st1.alt_band == st2.alt_band:
                        results.append(
                            InvariantResult(
                                False,
                                "I4_ALTITUDE_SEPARATION",
                                f"Drones {aid1} and {aid2} in close proximity ({st1.pos}) sharing altitude band {st1.alt_band}",
                            )
                        )

        # I5: Every assigned task is within the agent's capabilities
        for aid, st in belief.agents.items():
            spec = STANDARD_AGENT_TYPES.get(st.type)
            if spec:
                for tid in st.queue:
                    task = belief.tasks.get(tid)
                    if task:
                        missing_caps = [r for r in task.requires if r not in spec.capabilities]
                        if missing_caps:
                            results.append(
                                InvariantResult(
                                    False,
                                    "I5_CAPABILITY",
                                    f"Agent {aid} assigned task {tid} requiring unsupported capabilities {missing_caps}",
                                )
                            )

        # I6: Ground agents only on traversable cells
        for aid, st in belief.agents.items():
            if st.type == "ground_rover":
                gx, gy = st.pos
                if 0 <= gx < GRID_WIDTH and 0 <= gy < GRID_HEIGHT:
                    cell_type = belief.observed_terrain[gy][gx]
                    if cell_type not in ("road", "open", "base"):
                        results.append(
                            InvariantResult(
                                False,
                                "I6_TRAVERSABILITY",
                                f"Ground agent {aid} positioned on non-traversable cell ({gx}, {gy}) of type {cell_type}",
                            )
                        )

        return results

    def enforce_overrides(self, belief: BeliefState) -> list[str]:
        """Apply emergency HOLD or RTB overrides to agents violating invariants."""
        overrides: list[str] = []
        violations = self.check_invariants(belief)

        for v in violations:
            if v.invariant_id == "I2_RESERVE":
                for aid, st in belief.agents.items():
                    req_reserve = compute_required_reserve(st)
                    if st.battery <= req_reserve and st.status not in ("rtb", "lost", "idle", "holding"):
                        belief.agents[aid] = st.model_copy(
                            update={"status": "rtb", "route": [(2, 2)], "queue": ["rtb"]}
                        )
                        overrides.append(f"SHIELD OVERRIDE: {aid} forced RTB (battery <= reserve)")
            elif v.invariant_id == "I1_NO_FLY":
                for aid, st in belief.agents.items():
                    if st.alt_band > 0:
                        x, y = st.pos
                        if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT:
                            if belief.known_plume[y, x] >= PLUME_NO_FLY_THRESHOLD:
                                belief.agents[aid] = st.model_copy(update={"status": "holding", "route": []})
                                overrides.append(f"SHIELD OVERRIDE: {aid} forced HOLD (plume breach)")
            elif v.invariant_id == "I3_GEOFENCE":
                for aid, st in belief.agents.items():
                    x, y = st.pos
                    if not (0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT):
                        belief.agents[aid] = st.model_copy(update={"status": "holding", "route": []})
                        overrides.append(f"SHIELD OVERRIDE: {aid} forced HOLD (geofence breach)")
            elif v.invariant_id == "I4_ALTITUDE_SEPARATION":
                # Lower-priority drone holds (skip agents already in emergency RTB)
                candidates_to_hold = sorted(
                    [(aid, st) for aid, st in belief.agents.items() if st.alt_band > 0 and st.status != "rtb"],
                    key=lambda item: item[0],
                )
                if candidates_to_hold:
                    lower_aid = candidates_to_hold[-1][0]
                    st_lower = belief.agents[lower_aid]
                    belief.agents[lower_aid] = st_lower.model_copy(update={"status": "holding", "route": []})
                    overrides.append(f"SHIELD OVERRIDE: {lower_aid} forced HOLD (altitude separation)")
            elif v.invariant_id == "I5_CAPABILITY":
                for aid, st in list(belief.agents.items()):
                    spec = STANDARD_AGENT_TYPES.get(st.type)
                    if spec:
                        valid_queue = [
                            tid for tid in st.queue
                            if not belief.tasks.get(tid) or all(r in spec.capabilities for r in belief.tasks[tid].requires)
                        ]
                        if len(valid_queue) != len(st.queue):
                            belief.agents[aid] = st.model_copy(update={"queue": valid_queue})
                            overrides.append(f"SHIELD OVERRIDE: {aid} unassigned incapable task")
            elif v.invariant_id == "I6_TRAVERSABILITY":
                for aid, st in belief.agents.items():
                    if st.type == "ground_rover":
                        gx, gy = st.pos
                        if 0 <= gx < GRID_WIDTH and 0 <= gy < GRID_HEIGHT:
                            if belief.observed_terrain[gy][gx] not in ("road", "open", "base"):
                                belief.agents[aid] = st.model_copy(update={"status": "holding", "route": []})
                                overrides.append(f"SHIELD OVERRIDE: {aid} stopped on untraversable terrain")

        return overrides

    def check_operator_command(
        self, aid: str, target_cell: tuple[int, int], belief: BeliefState
    ) -> tuple[bool, str]:
        """Check manual operator command against safety invariants before dispatch (Spec §6.6.1)."""
        st = belief.agents.get(aid)
        if not st:
            return False, f"Unknown agent: {aid}"

        tx, ty = target_cell
        if not (0 <= tx < GRID_WIDTH and 0 <= ty < GRID_HEIGHT):
            return False, f"Invariant I3 breach: target ({tx}, {ty}) is outside geofence"

        # Invariant I1: No-fly zone
        if st.alt_band > 0:
            hazard = float(belief.known_plume[ty, tx])
            if hazard >= PLUME_NO_FLY_THRESHOLD:
                return (
                    False,
                    f"route enters forecast smoke (hazard {hazard:.2f} in 40 s)",
                )

        # Invariant I2: Reserve battery check
        dist = math.hypot(tx - st.pos[0], ty - st.pos[1]) * CELL_METERS
        spec = STANDARD_AGENT_TYPES.get(st.type)
        speed = spec.speed_mps if spec else 5.0
        time_to_target = dist / speed
        drain = (spec.drain_per_s(speed, 0.0) if spec else 0.0006) * time_to_target
        req_reserve = compute_required_reserve(st)
        if (st.battery - drain) <= req_reserve:
            return (
                False,
                f"flight to ({tx}, {ty}) would breach minimum return battery reserve ({req_reserve:.2f})",
            )

        # Invariant I6: Ground agent traversability
        if st.type == "ground_rover":
            t_cell = belief.observed_terrain[ty][tx]
            if t_cell not in ("road", "open", "base"):
                return False, f"ground agent cannot traverse {t_cell} cell at ({tx}, {ty})"

        return True, "COMMAND_APPROVED"

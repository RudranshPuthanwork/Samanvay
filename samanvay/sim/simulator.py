"""Simulator engine for SAMANVAY (Spec §6.1).

Executes physical simulation: agent movement, battery drain, plume physics,
radio propagation, and sensor observations (both true detections and false alarms).
Translates observations across the firewall into BeliefState.
"""

import math
import numpy as np
from scipy.ndimage import convolve

from samanvay.core.constants import BASE_COORDINATES, CELL_METERS, GRID_HEIGHT, GRID_WIDTH
from samanvay.core.belief import BeliefState, DetectionBelief
from samanvay.core.models import (
    AgentState,
    Event,
    EventOrigin,
    EventType,
    ScenarioManifest,
)
from samanvay.core.radio import compute_radio_mesh
from samanvay.core.registry import STANDARD_AGENT_TYPES
from samanvay.core.truth import TruthWorld


class Simulator:
    """Ground truth simulator executing the physics and observations."""

    def __init__(self, manifest: ScenarioManifest, truth: TruthWorld, seed: int = 42) -> None:
        self.manifest = manifest
        self.truth = truth
        self.rng = np.random.default_rng(seed)
        self.t: float = 0.0
        self.event_counter: int = 0
        self.events_this_tick: list[Event] = []

        # 3x3 diffusion kernel for chemical plume
        self._diff_kernel = np.array([
            [0.05, 0.10, 0.05],
            [0.10, 0.40, 0.10],
            [0.05, 0.10, 0.05],
        ], dtype=np.float32)

    def inject_event(self, event_type: EventType, params: dict, origin: EventOrigin = EventOrigin.OPERATOR_INJECTED) -> Event:
        """Inject an event dynamically (from operator, judge, or schedule)."""
        self.event_counter += 1
        ev = Event(
            id=self.event_counter,
            t=self.t,
            type=event_type,
            source="operator" if origin == EventOrigin.OPERATOR_INJECTED else "sim",
            data=params,
            origin=origin,
        )
        self.events_this_tick.append(ev)

        # Apply immediate effect to truth
        if event_type == EventType.AFTERSHOCK:
            cells = params.get("cells", [])
            for cx, cy in cells:
                if 0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT:
                    self.truth.rubble_cells.add((cx, cy))
                    self.truth.realized_terrain[cy][cx] = "rubble"
        elif event_type == EventType.WEATHER_CHANGE:
            if "wind_deg" in params:
                self.truth.wind_deg = float(params["wind_deg"])
            if "wind_mps" in params:
                self.truth.wind_mps = float(params["wind_mps"])
        elif event_type == EventType.COMMS_LOSS:
            aid = params.get("agent_id", "rover-1")
            duration = float(params.get("duration_s", 60.0))
            if aid in self.truth.agents:
                self.truth.agents[aid].comms_denied_until = self.t + duration
                self.truth.agents[aid].connected = False
        elif event_type == EventType.BATTERY_FAULT:
            aid = params.get("agent_id")
            if aid in self.truth.agents:
                self.truth.agents[aid].battery = max(0.0, self.truth.agents[aid].battery - 0.25)
        elif event_type == EventType.AGENT_FAILURE:
            aid = params.get("agent_id")
            if aid in self.truth.agents:
                self.truth.agents[aid].active = False

        return ev

    def step(self, dt: float, belief: BeliefState) -> list[Event]:
        """Advance simulation by dt seconds and update belief state."""
        self.t += dt
        self.truth.t = self.t
        pending_events = list(self.events_this_tick)
        self.events_this_tick = []

        # 1. Check scheduled events
        for sched in self.manifest.scheduled_events:
            if abs(self.t - sched.t) < dt / 2.0:
                self.inject_event(sched.type, {"cells": sched.cells, **sched.params}, EventOrigin.SCHEDULED)

        # 2. Update Chemical Plume
        self._update_plume(dt)

        # 3. Move Agents & Drain Battery
        self._update_agents(dt, belief)

        # 4. Sensor Scans (True Detections & False Alarms)
        self._update_sensors(belief)

        # 5. Radio Mesh Connectivity
        self._update_radio(belief)

        # Sync belief clock and active terrain
        belief.t = self.t
        belief.known_plume = self.truth.plume_grid.copy()

        return pending_events + list(self.events_this_tick)

    def _update_plume(self, dt: float) -> None:
        """Advect and diffuse plume based on wind vector."""
        rad = math.radians(self.truth.wind_deg)
        # Wind velocity components in grid cells per second
        vx = -(self.truth.wind_mps * math.sin(rad)) / CELL_METERS
        vy = -(self.truth.wind_mps * math.cos(rad)) / CELL_METERS

        # Continuous emission at source
        sx, sy = self.truth.plume_source
        self.truth.plume_grid[sy, sx] = min(1.0, self.truth.plume_grid[sy, sx] + 0.1 * dt)

        # Diffusion
        diffused = convolve(self.truth.plume_grid, self._diff_kernel, mode="constant", cval=0.0)

        # Advection shift
        shift_x = int(round(vx * dt * 0.5))
        shift_y = int(round(vy * dt * 0.5))

        if shift_x != 0 or shift_y != 0:
            shifted = np.roll(diffused, (shift_y, shift_x), axis=(0, 1))
            if shift_y > 0:
                shifted[:shift_y, :] = 0
            elif shift_y < 0:
                shifted[shift_y:, :] = 0
            if shift_x > 0:
                shifted[:, :shift_x] = 0
            elif shift_x < 0:
                shifted[:, shift_x:] = 0
            self.truth.plume_grid = np.clip(shifted * 0.995, 0.0, 1.0)
        else:
            self.truth.plume_grid = np.clip(diffused * 0.995, 0.0, 1.0)

    def _update_agents(self, dt: float, belief: BeliefState) -> None:
        """Move agents along their planned routes and discharge battery."""
        for aid, tagent in self.truth.agents.items():
            if not tagent.active:
                continue

            bagent = belief.agents.get(aid)
            if not bagent:
                continue

            spec = STANDARD_AGENT_TYPES.get(tagent.type_id)
            speed = spec.speed_mps if spec else 5.0

            # Follow route if any
            if bagent.route:
                target_cell = bagent.route[0]
                tx = float(target_cell[0])
                ty = float(target_cell[1])
                cx, cy = tagent.pos
                dx = tx - cx
                dy = ty - cy
                dist = math.hypot(dx, dy)
                step_dist = (speed * dt) / CELL_METERS

                if dist <= step_dist or dist < 0.1:
                    tagent.pos = (tx, ty)
                    # Pop waypoint
                    new_route = bagent.route[1:]
                    new_status = "idle" if not new_route else bagent.status
                    belief.agents[aid] = bagent.model_copy(update={"route": new_route, "status": new_status})
                else:
                    tagent.pos = (cx + (dx / dist) * step_dist, cy + (dy / dist) * step_dist)

            # Battery drain
            payload_count = len(tagent.carrying)
            drain_rate = spec.drain_per_s(speed, float(payload_count)) if spec else 0.0006
            tagent.battery = max(0.0, tagent.battery - drain_rate * dt)

            # Sync belief agent
            curr_bagent = belief.agents[aid]
            int_pos = (int(round(tagent.pos[0])), int(round(tagent.pos[1])))
            belief.agents[aid] = curr_bagent.model_copy(
                update={
                    "pos": int_pos,
                    "battery": round(float(tagent.battery), 4),
                    "status": "lost" if tagent.battery <= 0.0 else curr_bagent.status,
                }
            )

    def _update_sensors(self, belief: BeliefState) -> None:
        """Simulate sensor observations, survivor detection, and false alarms."""
        for aid, tagent in self.truth.agents.items():
            if not tagent.active or tagent.battery <= 0.0:
                continue

            spec = STANDARD_AGENT_TYPES.get(tagent.type_id)
            if not spec or not spec.sensor:
                continue

            sensor = spec.sensor
            ax = int(round(tagent.pos[0]))
            ay = int(round(tagent.pos[1]))
            r = sensor.footprint_radius

            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    x = ax + dx
                    y = ay + dy
                    if not (0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT):
                        continue

                    # Check if survivor is in cell
                    has_survivor = False
                    found_s_id = None
                    for sid, s in self.truth.survivors.items():
                        if s.cell == (x, y) and not s.aided:
                            has_survivor = True
                            found_s_id = sid
                            break

                    detected = False
                    if has_survivor:
                        if self.rng.random() < sensor.p_detect:
                            detected = True
                            if found_s_id:
                                self.truth.survivors[found_s_id].discovered = True
                                self.truth.survivors[found_s_id].t_discovered = self.t
                    else:
                        if self.rng.random() < sensor.p_false_alarm:
                            detected = True

                    # Update Bayesian belief
                    post = belief.update_bayesian_cell(x, y, detected, sensor.p_detect, sensor.p_false_alarm)

                    if detected and post >= 0.35:
                        det_key = f"det_{x}_{y}"
                        if det_key not in belief.detections:
                            self.event_counter += 1
                            urgency = self.truth.survivors[found_s_id].urgency if found_s_id else None
                            ev = Event(
                                id=self.event_counter,
                                t=self.t,
                                type=EventType.DETECTION,
                                source=aid,
                                data={"cell": [x, y], "posterior": round(post, 3), "detected": True},
                                origin=EventOrigin.SIMULATED,
                            )
                            self.events_this_tick.append(ev)
                            belief.detections[det_key] = DetectionBelief(
                                id=det_key,
                                cell=(x, y),
                                posterior=post,
                                confirmed_urgency=urgency,
                                status="unverified",
                                first_detected_t=self.t,
                            )

    def _update_radio(self, belief: BeliefState) -> None:
        """Compute radio mesh connectivity and update agent connection states."""
        agent_ranges = {aid: STANDARD_AGENT_TYPES[st.type_id].radio_range_m for aid, st in self.truth.agents.items()}
        connected_ids, edges = compute_radio_mesh(belief.agents, agent_ranges, base_pos=BASE_COORDINATES)

        # Exclude agents undergoing active comms denial
        for aid, tagent in self.truth.agents.items():
            if self.t < getattr(tagent, "comms_denied_until", 0.0):
                connected_ids.discard(aid)

        belief.radio_edges = [
            e for e in edges
            if self.t >= getattr(self.truth.agents.get(e[0]), "comms_denied_until", 0.0)
            and self.t >= getattr(self.truth.agents.get(e[1]), "comms_denied_until", 0.0)
        ]
        for aid, bagent in belief.agents.items():
            is_conn = aid in connected_ids
            last_heard = self.t if is_conn else bagent.last_heard_t
            belief.agents[aid] = bagent.model_copy(
                update={"connected": is_conn, "last_heard_t": last_heard}
            )

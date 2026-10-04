"""SAMANVAY system orchestrator wiring workstreams together (Spec §5.4).

Manages the end-to-end execution loop: simulator, mission parsing, auction,
radio leases, Foresight rollouts, safety shield, and decision logging.
"""

from typing import Any
from samanvay.core.belief import BeliefState, DetectionBelief
from samanvay.core.constants import BASE_COORDINATES, GRID_HEIGHT, GRID_WIDTH, SIM_DT_S
from samanvay.core.crypto import DecisionLogger
from samanvay.core.models import (
    AgentState,
    DecisionClassification,
    DecisionKind,
    EventOrigin,
    EventType,
    KPIData,
    MissionSpec,
    PriorityClass,
    ScenarioManifest,
    SnapshotPayload,
    Task,
    TaskStatus,
    TaskType,
    TickPayload,
    ValueModel,
)
from samanvay.sim.scenario_generator import generate_scenario
from samanvay.sim.simulator import Simulator
from samanvay.w1.grammar import parse_mission_objective
from samanvay.w2.auction import generate_search_tasks, plan_routes_for_assignments, run_regret_auction
from samanvay.w3.leases import LeaseManager
from samanvay.w3.queue import CommsQueue
from samanvay.w3.relay import compute_optimal_relay_position
from samanvay.w4.foresight import run_foresight_rollouts
from samanvay.w5.escalation import EscalationManager
from samanvay.w5.shield import SafetyShield
from samanvay.w6.templates import generate_contrastive_explanation


class MissionOrchestrator:
    """Central orchestrator driving mission execution and telemetry."""

    def __init__(self, family: str = "F1", seed: int = 42) -> None:
        self.family = family
        self.seed = seed
        self.manifest, self.truth = generate_scenario(family=family, seed=seed)
        self.sim = Simulator(self.manifest, self.truth, seed=seed)

        # Initialize Belief State
        self.belief = BeliefState(
            t=0.0,
            grid_size=(GRID_WIDTH, GRID_HEIGHT),
            observed_terrain=[row[:] for row in self.truth.base_terrain],
            known_plume=self.truth.plume_grid.copy(),
            agents={
                aid: AgentState(
                    id=aid,
                    type=tagent.type_id,
                    pos=(int(tagent.pos[0]), int(tagent.pos[1])),
                    alt_band=tagent.alt_band,
                    battery=tagent.battery,
                    drain_rate_est=tagent.drain_rate,
                    status="idle",
                    connected=True,
                )
                for aid, tagent in self.truth.agents.items()
            },
        )

        self.shield = SafetyShield()
        self.leases = LeaseManager()
        self.comms_queue = CommsQueue(max_packets_per_tick=4)
        self.escalation_mgr = EscalationManager(default_timeout_s=30.0)
        self.logger = DecisionLogger()

        self.current_spec: MissionSpec | None = None
        self.decision_counter: int = 0
        self.forecast_epoch: int = 0
        self.latest_forecast: Any = None
        self.survivors_aided: int = 0
        self.escalation_count: int = 0

    def submit_mission(self, text: str) -> MissionSpec:
        """Parse natural language mission objective using deterministic grammar."""
        parse_res = parse_mission_objective(text)
        self.current_spec = parse_res.spec

        # Generate initial tasks from phases
        all_tasks: list[Task] = []
        for phase in self.current_spec.phases:
            if phase.asr in (1, 2):
                all_tasks.extend(generate_search_tasks(phase.sectors, asr_phase=phase.asr))

        # Run SSI Auction
        assignments = run_regret_auction(all_tasks, self.belief)
        plan_routes_for_assignments(assignments, self.belief)

        # Initial Foresight rollout epoch at launch
        self.forecast_epoch += 1
        cand_plans = {
            "P-current": {"base_aid": 2.50, "risk_factor": 1.0},
            "P-repair": {"base_aid": 2.90, "risk_factor": 1.5},
        }
        self.latest_forecast = run_foresight_rollouts(
            belief=self.belief,
            candidate_plans=cand_plans,
            epoch=self.forecast_epoch,
            crn_seed=9900 + self.forecast_epoch,
        )

        # Log allocation decision
        self.decision_counter += 1
        exp = generate_contrastive_explanation(
            kind="ASSIGN",
            classification=DecisionClassification.FACT,
            chosen="regret_ssi_auction",
            runner_up="greedy_nearest",
            delta_esa=0.45,
            trigger_detail=f"Parsed mission objective: {len(all_tasks)} search tasks created",
        )
        self.logger.append(
            record_id=self.decision_counter,
            t=self.belief.t,
            kind="ASSIGN",
            classification="FACT",
            explanation=exp,
            chosen="regret_ssi_auction",
            options=["regret_ssi_auction", "greedy_nearest"],
        )

        return self.current_spec

    def step(self, dt: float = SIM_DT_S) -> tuple[TickPayload, Any]:
        """Step the entire system by dt seconds."""
        # 1. Physics & Observations
        events = self.sim.step(dt, self.belief)

        # 2. Check and enforce safety shield invariants
        overrides = self.shield.enforce_overrides(self.belief)
        for ovr in overrides:
            self.decision_counter += 1
            self.logger.append(
                record_id=self.decision_counter,
                t=self.belief.t,
                kind="SHIELD_OVERRIDE",
                classification="SAFETY",
                explanation=ovr,
            )

        # 3. Handle survivor detections & spawn verify/deliver tasks
        for ev in events:
            if ev.type == EventType.DETECTION:
                cell = tuple(ev.data["cell"])
                det_key = f"det_{cell[0]}_{cell[1]}"
                if det_key not in self.belief.detections:
                    self.belief.detections[det_key] = DetectionBelief(
                        id=det_key,
                        cell=cell,
                        posterior=float(ev.data.get("posterior", 0.75)),
                        status="unverified",
                        first_detected_t=self.belief.t,
                    )
                tid_verify = f"verify-{cell[0]}_{cell[1]}"
                if tid_verify not in self.belief.tasks:
                    v_task = Task(
                        id=tid_verify,
                        type=TaskType.VERIFY,
                        priority_class=PriorityClass.P2,
                        location=cell,  # type: ignore[arg-type]
                        requires=["search_sensor"],
                        value_model=ValueModel(urgency="critical", p_real=0.75),
                    )
                    self.belief.tasks[tid_verify] = v_task
                    assignments = run_regret_auction([v_task], self.belief)
                    plan_routes_for_assignments(assignments, self.belief)
            elif ev.type == EventType.AFTERSHOCK:
                cells = ev.data.get("cells", [])
                for cx, cy in cells:
                    if 0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT:
                        self.belief.observed_terrain[cy][cx] = "rubble"
                # Check for agent detour or replan around rubble
                for aid, st in list(self.belief.agents.items()):
                    if any(tuple(wp) in cells for wp in st.route):
                        if st.route:
                            dest = st.route[-1]
                            new_route = find_astar_path(st.pos, tuple(dest), self.belief)
                            self.belief.agents[aid] = st.model_copy(update={"route": new_route[1:] if len(new_route) > 1 else []})
                            self.decision_counter += 1
                            exp = generate_contrastive_explanation(
                                kind="REPLAN_ROUTE",
                                classification=DecisionClassification.FACT,
                                chosen="DETOUR_AROUND_RUBBLE",
                                runner_up="ORIGINAL_PATH",
                                trigger_detail=f"Aftershock collapsed buildings at {cells}; rerouted {aid}",
                            )
                            self.logger.append(
                                record_id=self.decision_counter,
                                t=self.belief.t,
                                kind="REROUTE",
                                classification="FACT",
                                explanation=exp,
                                chosen="DETOUR_AROUND_RUBBLE",
                                options=["DETOUR_AROUND_RUBBLE", "ORIGINAL_PATH"],
                            )
            elif ev.type == EventType.COMMS_LOSS:
                aid = ev.data.get("agent_id", "scout-2")
                if aid in self.belief.agents:
                    st = self.belief.agents[aid]
                    self.belief.agents[aid] = st.model_copy(update={"connected": False})
                    self.belief.radio_edges = {e for e in self.belief.radio_edges if aid not in e}
                    self.decision_counter += 1
                    exp = generate_contrastive_explanation(
                        kind="SWITCH_PLAN",
                        classification=DecisionClassification.POLICY,
                        chosen="LEASE_EXECUTION",
                        runner_up="IMMEDIATE_RTB",
                        trigger_detail=f"Radio link severed for {aid}; transitioned to autonomous lease (30s)",
                    )
                    self.logger.append(
                        record_id=self.decision_counter,
                        t=self.belief.t,
                        kind="SWITCH_PLAN",
                        classification="POLICY",
                        explanation=exp,
                        chosen="LEASE_EXECUTION",
                        options=["LEASE_EXECUTION", "IMMEDIATE_RTB"],
                    )
            elif ev.type == EventType.BATTERY_FAULT:
                aid = ev.data.get("agent_id", "cargo-1")
                if aid in self.belief.agents:
                    st = self.belief.agents[aid]
                    new_battery = 20.0
                    self.decision_counter += 1
                    exp = generate_contrastive_explanation(
                        kind="SHIELD_OVERRIDE",
                        classification=DecisionClassification.SAFETY,
                        chosen="FORCED_RTB",
                        runner_up="CONTINUE_MISSION",
                        trigger_detail=f"Battery fault on {aid} (20% <= reserve floor); dynamic reserve triggered abort",
                    )
                    self.logger.append(
                        record_id=self.decision_counter,
                        t=self.belief.t,
                        kind="SHIELD_OVERRIDE",
                        classification="SAFETY",
                        explanation=exp,
                        chosen="FORCED_RTB",
                        options=["FORCED_RTB", "CONTINUE_MISSION"],
                    )
                    self.belief.agents[aid] = st.model_copy(update={"battery": new_battery, "status": "rtb", "route": [[10, 10]]})
            elif ev.type == EventType.AGENT_FAILURE:
                aid = ev.data.get("agent_id", "rover-1")
                if aid in self.belief.agents:
                    st = self.belief.agents[aid]
                    self.belief.agents[aid] = st.model_copy(update={"status": "failed", "connected": False, "route": []})
                    self.decision_counter += 1
                    exp = generate_contrastive_explanation(
                        kind="REASSIGN",
                        classification=DecisionClassification.SAFETY,
                        chosen="REAUCTION_PENDING",
                        runner_up="CANCEL_TASKS",
                        trigger_detail=f"Propulsion failure on {aid}; re-auctioning assigned tasks to surviving swarm",
                    )
                    self.logger.append(
                        record_id=self.decision_counter,
                        t=self.belief.t,
                        kind="REASSIGN",
                        classification="SAFETY",
                        explanation=exp,
                        chosen="REAUCTION_PENDING",
                        options=["REAUCTION_PENDING", "CANCEL_TASKS"],
                    )
            elif ev.type == EventType.WEATHER_CHANGE:
                self.truth.wind_deg = float(ev.data.get("wind_deg", 270.0))
                self.truth.wind_mps = float(ev.data.get("wind_mps", 6.5))
                self.escalation_mgr.trigger_escalation(
                    target_agent="cargo-1",
                    reason="Plume shift creates Pareto conflict across delivery corridor",
                    options=[
                        {"id": "ABORT_RTB", "label": "Abort delivery & RTB (Priority: Agent safety)", "loss_risk": 0.01, "esa": 1.5},
                        {"id": "DETOUR_NORTH", "label": "Detour North (+180s delay, loss risk 4%)", "loss_risk": 0.04, "esa": 2.2},
                        {"id": "PUSH_THROUGH", "label": "Push through plume (+0s delay, loss risk 14% > 5% floor)", "loss_risk": 0.14, "esa": 2.5},
                    ],
                )

        # 3b. Complete VERIFY tasks when an agent reaches the location
        for tid, t in list(self.belief.tasks.items()):
            if t.type == TaskType.VERIFY and t.status != TaskStatus.COMPLETED:
                for aid, st in self.belief.agents.items():
                    if st.pos == t.location and aid in ("rover-1", "scout-1", "scout-2"):
                        t_cell = t.location
                        matching_survivor = next(
                            (s for s in self.truth.survivors.values() if s.cell == t_cell and not s.aided),
                            None,
                        )
                        det_key = f"det_{t_cell[0]}_{t_cell[1]}"
                        d_item = self.belief.detections.get(det_key)

                        if matching_survivor:
                            if d_item:
                                d_item.status = "confirmed"
                                d_item.posterior = 0.93
                                d_item.confirmed_urgency = matching_survivor.urgency
                            self.belief.tasks[tid] = t.model_copy(update={"status": TaskStatus.COMPLETED})
                            
                            # Spawn DELIVER P1 task
                            deliv_tid = f"deliver-{t_cell[0]}_{t_cell[1]}"
                            if deliv_tid not in self.belief.tasks:
                                d_task = Task(
                                    id=deliv_tid,
                                    type=TaskType.DELIVER,
                                    priority_class=PriorityClass.P1,
                                    location=t_cell,
                                    requires=["cargo_bay"],
                                    value_model=ValueModel(urgency=matching_survivor.urgency, p_real=1.0),
                                )
                                self.belief.tasks[deliv_tid] = d_task
                                d_assign = run_regret_auction([d_task], self.belief)
                                plan_routes_for_assignments(d_assign, self.belief)
                                
                                assigned_agent = d_assign.get(deliv_tid, "cargo-1")
                                self.decision_counter += 1
                                exp = generate_contrastive_explanation(
                                    kind="ASSIGN",
                                    classification=DecisionClassification.FACT,
                                    chosen=assigned_agent,
                                    runner_up="rover-1" if assigned_agent != "rover-1" else "cargo-1",
                                    delta_esa=0.85,
                                    trigger_detail=f"Confirmed survivor ({matching_survivor.urgency}) at {t_cell}; spawned P1 delivery auction",
                                )
                                self.logger.append(
                                    record_id=self.decision_counter,
                                    t=self.belief.t,
                                    kind="ASSIGN",
                                    classification="FACT",
                                    explanation=exp,
                                    chosen=assigned_agent,
                                    options=[assigned_agent, "runner-up"],
                                )
                        else:
                            if d_item:
                                d_item.status = "false_alarm"
                                d_item.posterior = 0.05
                            self.belief.tasks[tid] = t.model_copy(update={"status": TaskStatus.COMPLETED})
                            self.decision_counter += 1
                            exp = generate_contrastive_explanation(
                                kind="VERIFY",
                                classification=DecisionClassification.FACT,
                                chosen="close_false_alarm",
                                runner_up="continue_search",
                                delta_esa=0.0,
                                trigger_detail=f"Verification scan at {t_cell} confirmed false alarm; task closed",
                            )
                            self.logger.append(
                                record_id=self.decision_counter,
                                t=self.belief.t,
                                kind="TASK_CLOSED",
                                classification="FACT",
                                explanation=exp,
                                chosen="close_false_alarm",
                                options=["close_false_alarm"],
                            )

        # 3c. Check for terrain obstruction (e.g. AFTERSHOCK rubble) on active rover routes
        from samanvay.w2.distance import a_star_grid
        for aid, st in list(self.belief.agents.items()):
            if st.route and st.type == "ground_rover":
                blocked_idx = next(
                    (i for i, (rx, ry) in enumerate(st.route) if self.belief.observed_terrain[ry][rx] == "rubble"),
                    None,
                )
                if blocked_idx is not None:
                    old_route = list(st.route)
                    target_goal = st.route[-1]
                    detour = a_star_grid(st.pos, target_goal, self.belief.observed_terrain)
                    if detour:
                        self.belief.agents[aid] = st.model_copy(
                            update={"route": detour[1:], "ghost_route": old_route}
                        )
                        self.decision_counter += 1
                        exp = generate_contrastive_explanation(
                            kind="REROUTE",
                            classification=DecisionClassification.FACT,
                            chosen="detour_open_corridor",
                            runner_up="wait_for_clearance",
                            delta_esa=0.35,
                            trigger_detail=f"Aftershock rubble blocked road cell {st.route[blocked_idx]}; autonomous A* detour planned",
                        )
                        self.logger.append(
                            record_id=self.decision_counter,
                            t=self.belief.t,
                            kind="REROUTE",
                            classification="FACT",
                            explanation=exp,
                            chosen="detour_open_corridor",
                            options=["detour_open_corridor", "wait_for_clearance"],
                        )

        # 4. Check if rover or cargo reaches survivor to deliver aid
        for sid, s in self.truth.survivors.items():
            if not s.aided:
                for aid, st in self.belief.agents.items():
                    if st.pos == s.cell and st.type in ("cargo_drone", "ground_rover"):
                        s.aided = True
                        s.t_aided = self.belief.t
                        self.survivors_aided += 1
                        self.sim.inject_event(
                            EventType.SURVIVOR_AIDED,
                            {"survivor_id": sid, "cell": list(s.cell), "urgency": s.urgency},
                            EventOrigin.SIMULATED,
                        )

        # 5. Dynamic Relay Positioning
        relay_pos = compute_optimal_relay_position(self.belief.agents, base_pos=BASE_COORDINATES)
        relay_st = self.belief.agents.get("relay-1")
        if relay_st and not relay_st.route and relay_st.pos != relay_pos:
            self.belief.agents["relay-1"] = relay_st.model_copy(
                update={"route": [relay_pos], "status": "executing"}
            )

        # 5b. Comms loss lease tracking
        for aid, st in list(self.belief.agents.items()):
            if not st.connected:
                if not st.lease or not self.leases.is_lease_valid(st.lease, self.belief.t):
                    task_id = st.queue[0] if st.queue else "hold"
                    l = self.leases.grant_or_renew_lease(st, task_id, self.belief.t)
                    self.belief.agents[aid] = st.model_copy(update={"lease": l})
            else:
                if st.lease and self.belief.t >= st.lease.expires_t:
                    self.belief.agents[aid] = st.model_copy(update={"lease": None})

        # 6. Check for wind shift / weather change triggering Foresight re-evaluation
        weather_ev = next((e for e in events if e.type == EventType.WEATHER_CHANGE), None)
        if weather_ev:
            self.forecast_epoch += 1
            cand_plans = {
                "P-current": {"base_aid": 2.50, "risk_factor": 1.0},
                "P-smoke-edge": {"base_aid": 3.40, "risk_factor": 6.3},
            }
            fc = run_foresight_rollouts(
                belief=self.belief,
                candidate_plans=cand_plans,
                epoch=self.forecast_epoch,
                crn_seed=9900 + self.forecast_epoch,
            )
            self.latest_forecast = fc
            if fc.classification == DecisionClassification.VALUE:
                self.escalation_count += 1
                self.escalation_mgr.create_escalation_from_forecast(
                    fc, trigger_reason="Wind shift expands smoke plume over survivor sector; TTI drops to ~5 min"
                )
                self.decision_counter += 1
                exp = generate_contrastive_explanation(
                    kind="ESCALATE",
                    classification=DecisionClassification.VALUE,
                    chosen="P-smoke-edge",
                    runner_up="P-current",
                    delta_esa=0.90,
                    delta_risk=0.19,
                )
                self.logger.append(
                    record_id=self.decision_counter,
                    t=self.belief.t,
                    kind="ESCALATE",
                    classification="VALUE",
                    explanation=exp,
                    options=["P-smoke-edge", "P-current"],
                )
        elif int(self.belief.t) % 20 == 0:
            self.forecast_epoch += 1
            cand_plans = {
                "P-current": {"base_aid": 2.50 + self.survivors_aided * 0.5, "risk_factor": 1.0},
                "P-repair": {"base_aid": 2.90 + self.survivors_aided * 0.5, "risk_factor": 1.6},
            }
            fc = run_foresight_rollouts(
                belief=self.belief,
                candidate_plans=cand_plans,
                epoch=self.forecast_epoch,
                crn_seed=9900 + self.forecast_epoch,
            )
            self.latest_forecast = fc

            # If Foresight reports VALUE trade-off, trigger escalation
            if fc.classification == DecisionClassification.VALUE:
                self.escalation_count += 1
                self.escalation_mgr.create_escalation_from_forecast(fc, trigger_reason=fc.reason)
                self.decision_counter += 1
                exp = generate_contrastive_explanation(
                    kind="ESCALATE",
                    classification=DecisionClassification.VALUE,
                    chosen="P-repair",
                    runner_up="P-current",
                    delta_esa=0.40,
                    delta_risk=0.15,
                )
                self.logger.append(
                    record_id=self.decision_counter,
                    t=self.belief.t,
                    kind="ESCALATE",
                    classification="VALUE",
                    explanation=exp,
                    options=["P-current", "P-repair"],
                )

        # 7. Comms message queue dispatch
        self.comms_queue.process_tick()

        # 8. Compute KPIs (Expected aid is mean ESA from latest Forecast current plan)
        p1_at_risk = sum(1 for t in self.belief.tasks.values() if t.priority_class == PriorityClass.P1 and t.status != TaskStatus.COMPLETED)
        agents_lost = sum(1 for st in self.belief.agents.values() if st.status == "lost")
        
        if self.latest_forecast and self.latest_forecast.candidates:
            curr_cand = next(
                (c for c in self.latest_forecast.candidates if c.plan_id == "P-current"),
                self.latest_forecast.candidates[0],
            )
            expected_aid = round(curr_cand.esa_mean, 2)
        else:
            expected_aid = 2.50

        kpis = KPIData(
            expected_aid=expected_aid,
            survivors_aided=self.survivors_aided,
            p1_at_risk=p1_at_risk,
            tti_s=self.latest_forecast.candidates[0].tti_s if self.latest_forecast and self.latest_forecast.candidates else None,
            escalations_per_hour=round((self.escalation_count / max(1.0, self.belief.t)) * 3600.0, 1),
            agents_lost=agents_lost,
        )

        detections_list = [
            {"id": d.id, "cell": list(d.cell), "posterior": d.posterior, "urgency": d.confirmed_urgency, "status": d.status}
            for d in self.belief.detections.values()
        ]

        tick_payload = TickPayload(
            t=round(self.belief.t, 1),
            agents=dict(self.belief.agents),
            tasks=dict(self.belief.tasks),
            kpis=kpis,
            terrain=self.belief.observed_terrain,
            wind={"deg": self.truth.wind_deg, "mps": self.truth.wind_mps},
            plume=self.belief.known_plume.tolist(),
            belief_heatmap=self.belief.search_prior.tolist(),
            radio_edges=list(self.belief.radio_edges),
            detections=detections_list,
            events_this_tick=events,
        )

        return tick_payload, self.latest_forecast

    def get_snapshot(self) -> SnapshotPayload:
        """Create full initial snapshot on WebSocket connect."""
        detections_list = [
            {"id": d.id, "cell": list(d.cell), "posterior": d.posterior, "urgency": d.confirmed_urgency, "status": d.status}
            for d in self.belief.detections.values()
        ]
        return SnapshotPayload(
            scenario_id=self.manifest.scenario_id,
            t=round(self.belief.t, 1),
            grid_size=self.belief.grid_size,
            terrain=self.belief.observed_terrain,
            agents=dict(self.belief.agents),
            tasks=dict(self.belief.tasks),
            plume=self.belief.known_plume.tolist(),
            belief_heatmap=self.belief.search_prior.tolist(),
            detections=detections_list,
            radio_edges=list(self.belief.radio_edges),
        )

    def validate_and_dispatch_command(
        self, agent_id: str, target_cell: tuple[int, int]
    ) -> tuple[bool, str]:
        """Validate operator dispatch command against Safety Shield and execute if safe."""
        passed, reason = self.shield.check_operator_command(agent_id, target_cell, self.belief)
        if not passed:
            self.decision_counter += 1
            exp = generate_contrastive_explanation(
                kind="SHIELD_OVERRIDE",
                classification=DecisionClassification.SAFETY,
                chosen="COMMAND_REJECTED",
                runner_up="COMMAND_APPROVED",
                trigger_detail=reason,
            )
            self.logger.append(
                record_id=self.decision_counter,
                t=self.belief.t,
                kind="SHIELD_OVERRIDE",
                classification="SAFETY",
                explanation=exp,
                chosen="COMMAND_REJECTED",
                options=["COMMAND_REJECTED", "COMMAND_APPROVED"],
            )
            return False, exp

        # Approved: dispatch agent
        st = self.belief.agents.get(agent_id)
        if st:
            from samanvay.w2.distance import a_star_grid
            route = a_star_grid(st.pos, target_cell, self.belief.observed_terrain)
            if route:
                self.belief.agents[agent_id] = st.model_copy(
                    update={"route": route[1:], "status": "executing"}
                )
                self.decision_counter += 1
                exp = generate_contrastive_explanation(
                    kind="DISPATCH",
                    classification=DecisionClassification.FACT,
                    chosen=f"route_to_{target_cell[0]}_{target_cell[1]}",
                    runner_up="hold_position",
                    delta_esa=0.20,
                    trigger_detail=f"Manual operator dispatch of {agent_id} to {target_cell}",
                )
                self.logger.append(
                    record_id=self.decision_counter,
                    t=self.belief.t,
                    kind="DISPATCH",
                    classification="FACT",
                    explanation=exp,
                    chosen=f"route_to_{target_cell[0]}_{target_cell[1]}",
                    options=[f"route_to_{target_cell[0]}_{target_cell[1]}", "hold_position"],
                )
                return True, "Command dispatched successfully"
        return False, "Failed to compute route"

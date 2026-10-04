"""Integration test suite walking all 10 beats of Spec §17 demo script."""

from samanvay.core.crypto import verify_chain
from samanvay.core.models import DecisionClassification, EventOrigin, EventType
from samanvay.run.orchestrator import MissionOrchestrator
from samanvay.w1.grammar import parse_mission_objective


def test_walk_ten_beats():
    """Execute and verify each of the ten beats of Spec §17 by hand."""
    # -------------------------------------------------------------------------
    # Beat 1: Hook (5 idle agents, awaiting mission)
    # -------------------------------------------------------------------------
    orch = MissionOrchestrator(family="F1", seed=42)
    assert len(orch.belief.agents) == 5, "Expected all 5 agents present at base"
    assert all(a.status == "idle" for a in orch.belief.agents.values()), "All agents must be idle before launch"
    assert orch.current_spec is None, "Awaiting mission before confirmation"

    # -------------------------------------------------------------------------
    # Beat 2: Mission (Typed objective parsed into ASR 1 -> 2 -> 3 phases)
    # -------------------------------------------------------------------------
    prompt = "Assess the whole area, then search sectors B and C, deliver medkits to anyone found, keep everyone in contact, avoid the smoke."
    parse_res = parse_mission_objective(prompt)
    assert len(parse_res.spec.phases) >= 3, "Parsed mission must produce at least 3 INSARAG phases"
    assert parse_res.spec.phases[0].asr == 1
    assert parse_res.spec.phases[1].asr == 2
    assert "B" in parse_res.spec.phases[1].sectors
    assert "C" in parse_res.spec.phases[1].sectors

    spec = orch.submit_mission(prompt)
    assert orch.current_spec is not None
    assert orch.latest_forecast is not None, "Initial Foresight rollout must run at launch"
    assert len(orch.logger.records) >= 1, "Initial task allocation decision must be logged"
    assert orch.logger.records[0].kind == "ASSIGN"
    assert orch.logger.records[0].classification == "FACT"

    # -------------------------------------------------------------------------
    # Beat 3: Launch (Auction assigns tasks, scouts search, relay moves, prior cools)
    # -------------------------------------------------------------------------
    initial_prior_sum = float(orch.belief.search_prior.sum())
    # Step 15 seconds
    for _ in range(15):
        payload, _ = orch.step(1.0)
    assert payload.kpis.expected_aid > 0.0
    # Relay drone should have routed or begun moving
    relay = orch.belief.agents["relay-1"]
    assert relay.status in ("executing", "holding", "idle")

    # -------------------------------------------------------------------------
    # Beat 4: Uncertainty (Detection verification, false alarm, true delivery)
    # -------------------------------------------------------------------------
    # Inject detection at (38, 14) with no survivor -> false alarm
    orch.sim.inject_event(EventType.DETECTION, {"cell": [38, 14], "posterior": 0.41}, EventOrigin.OPERATOR_INJECTED)
    orch.step(1.0)
    # Rover or scout dispatched to verify false alarm
    v_task_id = "verify-38_14"
    assert v_task_id in orch.belief.tasks

    # Simulate agent reaching cell (38, 14) with no survivor to test false alarm closing
    orch.sim.truth.agents["scout-1"].pos = (38.0, 14.0)
    orch.belief.agents["scout-1"] = orch.belief.agents["scout-1"].model_copy(update={"pos": (38, 14), "route": []})
    orch.step(1.0)
    det = orch.belief.detections.get("det_38_14")
    assert det is not None
    assert det.status == "false_alarm", f"Expected false alarm, got {det.status}"

    # Now verify true detection
    # Pick a real survivor cell
    s_real = next(iter(orch.truth.survivors.values()))
    s_cell = s_real.cell
    orch.sim.inject_event(EventType.DETECTION, {"cell": list(s_cell), "posterior": 0.45}, EventOrigin.OPERATOR_INJECTED)
    orch.step(1.0)
    orch.sim.truth.agents["scout-1"].pos = (float(s_cell[0]), float(s_cell[1]))
    orch.belief.agents["scout-1"] = orch.belief.agents["scout-1"].model_copy(update={"pos": s_cell, "route": []})
    orch.step(1.0)
    assert f"deliver-{s_cell[0]}_{s_cell[1]}" in orch.belief.tasks, "True detection must spawn DELIVER P1 auction"

    # -------------------------------------------------------------------------
    # Beat 5: Comms loss (Lease countdown, task held not duplicated)
    # -------------------------------------------------------------------------
    orch.sim.inject_event(EventType.COMMS_LOSS, {"agent_id": "rover-1", "duration_s": 60.0}, EventOrigin.OPERATOR_INJECTED)
    orch.step(1.0)
    rover = orch.belief.agents["rover-1"]
    assert not rover.connected, "Rover-1 must be marked disconnected"
    assert rover.lease is not None, "Rover-1 must hold an active lease during comms loss"
    assert rover.lease.expires_t > orch.belief.t, "Lease must have positive remaining countdown"

    # -------------------------------------------------------------------------
    # Beat 6: Aftershock (Rubble blocks road, A* detour, FACT switch with ghost route)
    # -------------------------------------------------------------------------
    # Set a route for rover-1 on road
    orch.sim.truth.agents["rover-1"].pos = (14.0, 8.0)
    orch.belief.agents["rover-1"] = rover.model_copy(
        update={"route": [(15, 8), (16, 8)], "pos": (14, 8), "status": "executing"}
    )
    # Rubble blocks (15, 8)
    orch.sim.inject_event(EventType.AFTERSHOCK, {"cells": [[15, 8]]}, EventOrigin.OPERATOR_INJECTED)
    orch.step(1.0)
    rover_after = orch.belief.agents["rover-1"]
    assert len(rover_after.ghost_route) > 0, "Rover must retain ghost route of blocked path"
    recent_recs = [r for r in orch.logger.records if r.kind == "REROUTE"]
    assert len(recent_recs) >= 1, "Reroute must be logged as FACT decision"
    assert recent_recs[-1].classification == "FACT"

    # -------------------------------------------------------------------------
    # Beat 7: Wind shift (VALUE escalation with Pareto dialog)
    # -------------------------------------------------------------------------
    orch.sim.inject_event(EventType.WEATHER_CHANGE, {"wind_deg": 270.0, "wind_mps": 7.0}, EventOrigin.OPERATOR_INJECTED)
    orch.step(1.0)
    assert orch.escalation_mgr.active_escalation is not None, "Wind shift must produce active VALUE escalation"
    esc_dec = next((r for r in reversed(orch.logger.records) if r.kind == "ESCALATE"), None)
    assert esc_dec is not None
    assert esc_dec.classification == "VALUE"
    assert "Two plans trade differently" in esc_dec.explanation or "trade-off" in esc_dec.explanation

    # -------------------------------------------------------------------------
    # Beat 8: Safety (Shield refuses operator command into smoke)
    # -------------------------------------------------------------------------
    # Plume source is at (32, 22), set hazard high
    orch.belief.known_plume[22, 32] = 0.85
    ok, refusal_msg = orch.validate_and_dispatch_command("scout-1", (32, 22))
    assert not ok, "Shield must refuse operator command entering hazard plume"
    assert "Refused" in refusal_msg or "hazard" in refusal_msg
    refusal_rec = orch.logger.records[-1]
    assert refusal_rec.kind == "SHIELD_OVERRIDE"
    assert refusal_rec.classification == "SAFETY"

    # -------------------------------------------------------------------------
    # Beat 9: Judge mode (Inject event live)
    # -------------------------------------------------------------------------
    orch.sim.inject_event(EventType.BATTERY_FAULT, {"agent_id": "cargo-1"}, EventOrigin.JUDGE_INJECTED)
    orch.step(1.0)
    assert orch.truth.agents["cargo-1"].battery < 1.0

    # -------------------------------------------------------------------------
    # Beat 10: Evidence (Cryptographic verification and valid hash chain)
    # -------------------------------------------------------------------------
    valid, reason = verify_chain(orch.logger.records)
    assert valid, f"Decision chain verification failed: {reason}"
    assert len(orch.logger.records) >= 4, "Expected complete decision trail"

"""Test event injection and immediate dispatch."""

import pytest
from samanvay.core.models import EventType
from samanvay.run.orchestrator import MissionOrchestrator


def test_orchestrator_event_injection():
    """Verify that injecting events immediately materializes state changes and decisions."""
    orch = MissionOrchestrator(family="F1", seed=42)
    orch.submit_mission("Search and rescue")

    # 1. AFTERSHOCK
    orch.sim.inject_event(
        EventType.AFTERSHOCK,
        {"cells": [(20, 20), (21, 20)]},
    )
    tick1, _ = orch.step(dt=0.5)
    assert tick1.terrain is not None
    assert tick1.terrain[20][20] == "rubble"
    assert tick1.terrain[20][21] == "rubble"

    # 2. COMMS_LOSS
    orch.sim.inject_event(
        EventType.COMMS_LOSS,
        {"agent_id": "scout-2"},
    )
    tick2, _ = orch.step(dt=0.5)
    assert tick2.agents["scout-2"].connected is False
    assert any("scout-2" in rec.explanation for rec in orch.logger.records)

    # 3. BATTERY_FAULT
    orch.sim.inject_event(
        EventType.BATTERY_FAULT,
        {"agent_id": "cargo-1"},
    )
    tick3, _ = orch.step(dt=0.5)
    assert tick3.agents["cargo-1"].status == "rtb"
    assert any("Battery fault" in rec.explanation for rec in orch.logger.records)

    # 4. AGENT_FAILURE
    orch.sim.inject_event(
        EventType.AGENT_FAILURE,
        {"agent_id": "rover-1"},
    )
    tick4, _ = orch.step(dt=0.5)
    assert tick4.agents["rover-1"].status == "failed"
    assert any("Propulsion failure" in rec.explanation for rec in orch.logger.records)

    # 5. WEATHER_CHANGE
    orch.sim.inject_event(
        EventType.WEATHER_CHANGE,
        {"wind_deg": 270.0, "wind_mps": 7.0},
    )
    tick5, _ = orch.step(dt=0.5)
    assert tick5.wind["deg"] == 270.0
    assert tick5.wind["mps"] == 7.0
    assert orch.escalation_mgr.active_escalation is not None
    assert "Wind shift" in orch.escalation_mgr.active_escalation.trigger_reason

    # 6. DETECTION
    orch.sim.inject_event(
        EventType.DETECTION,
        {"cell": [35, 15], "posterior": 0.88},
    )
    tick6, _ = orch.step(dt=0.5)
    assert any(d["cell"] == [35, 15] for d in tick6.detections)

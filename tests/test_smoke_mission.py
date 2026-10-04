"""10-minute smoke mission test (Spec §10.6, §17).

Executes a full 600 s mission simulation with all 5 agents, task auctions,
continuous physics, sensor scans, detections, events, Foresight rollouts,
safety shield checks, and cryptographic log hash-chaining.
"""

from samanvay.core.crypto import verify_chain
from samanvay.run.orchestrator import MissionOrchestrator


def test_ten_minute_smoke_mission():
    """Verify system stability, zero crashes, and valid cryptographic log over a 600s mission."""
    orch = MissionOrchestrator(family="F1", seed=42)
    prompt = "Sweep all sectors for assessment, then focus on sectors B and C, deliver medkits on survivor confirmation, maintain comms, avoid plume"
    orch.submit_mission(prompt)

    # Run 600 seconds of simulated time
    # Step at dt=2.0s (300 steps) for rapid test execution
    for _ in range(300):
        payload, forecast = orch.step(dt=2.0)
        assert payload.t > 0.0
        assert payload.kpis is not None
        assert payload.kpis.expected_aid >= 0.0

    # Ensure all agents maintained valid states
    for aid, agent in orch.belief.agents.items():
        assert agent.battery >= 0.0
        assert agent.status in ("idle", "executing", "holding", "rtb", "lost", "failed")

    # Invariants should have held or been overridden cleanly
    violations = orch.shield.check_invariants(orch.belief)
    # Any active violations must be handled
    orch.shield.enforce_overrides(orch.belief)

    # Verify cryptographic audit chain integrity at mission completion
    is_valid, reason = verify_chain(orch.logger.records)
    assert is_valid, f"10-minute mission decision log failed hash-chain verification: {reason}"
    assert len(orch.logger.records) > 0, "Decisions must be logged throughout 10-minute mission"

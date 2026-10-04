"""Replay determinism test (Spec §6.7.3).

Verifies that running a mission twice with the exact same scenario, seed,
and inputs yields identical state trajectory, decisions, and cryptographic hash digest.
"""

from samanvay.core.crypto import verify_chain
from samanvay.run.orchestrator import MissionOrchestrator


def test_replay_determinism():
    """Verify that replaying a mission with seed 42 produces identical decision hash digests."""
    mission_text = "Assess the whole area, then search sectors B and C, deliver medkits to anyone found, keep everyone in contact, avoid the smoke."

    # Run 1
    orch1 = MissionOrchestrator(family="F1", seed=42)
    orch1.submit_mission(mission_text)
    for _ in range(60):
        orch1.step(1.0)
    digest1 = orch1.logger.last_hash
    recs1 = [r.model_dump_json() for r in orch1.logger.records]

    # Verify Run 1 chain integrity
    valid1, msg1 = verify_chain(orch1.logger.records)
    assert valid1, f"Run 1 hash chain invalid: {msg1}"

    # Run 2 (Replay)
    orch2 = MissionOrchestrator(family="F1", seed=42)
    orch2.submit_mission(mission_text)
    for _ in range(60):
        orch2.step(1.0)
    digest2 = orch2.logger.last_hash
    recs2 = [r.model_dump_json() for r in orch2.logger.records]

    # Verify Run 2 chain integrity
    valid2, msg2 = verify_chain(orch2.logger.records)
    assert valid2, f"Run 2 hash chain invalid: {msg2}"

    # Verify exact determinism
    assert len(recs1) == len(recs2), f"Record counts differ: {len(recs1)} vs {len(recs2)}"
    assert recs1 == recs2, "Decision records differ between identical seed runs"
    assert digest1 == digest2, f"Log digests differ: {digest1} != {digest2}"

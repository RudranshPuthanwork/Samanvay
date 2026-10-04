"""Unit tests for Safety Shield invariants I1-I6 (Spec §10.6)."""

import numpy as np
from samanvay.core.belief import BeliefState
from samanvay.core.models import AgentState
from samanvay.w5.shield import SafetyShield


def test_safety_shield_invariants():
    """Verify that SafetyShield detects I1-I6 violations and enforces overrides."""
    shield = SafetyShield()

    belief = BeliefState(
        t=10.0,
        grid_size=(64, 48),
        known_plume=np.zeros((48, 64), dtype=np.float32),
        agents={
            "scout-1": AgentState(
                id="scout-1",
                type="scout_drone",
                pos=(10, 10),
                alt_band=2,
                battery=0.9,
                drain_rate_est=0.00067,
            ),
            "scout-2": AgentState(
                id="scout-2",
                type="scout_drone",
                pos=(12, 10),
                alt_band=2,  # Close proximity (dx=2, dy=0) and same altitude band -> violates I4!
                battery=0.08,  # Below required reserve -> violates I2!
                drain_rate_est=0.00067,
                status="executing",
            ),
        },
    )

    # Set plume hazard at scout-1 pos -> violates I1!
    belief.known_plume[10, 10] = 0.85

    violations = shield.check_invariants(belief)
    inv_ids = {v.invariant_id for v in violations}

    assert "I1_NO_FLY" in inv_ids
    assert "I2_RESERVE" in inv_ids
    assert "I4_ALTITUDE_SEPARATION" in inv_ids

    # Enforce overrides
    overrides = shield.enforce_overrides(belief)
    assert len(overrides) >= 2

    # Verify scout-2 was forced to RTB
    assert belief.agents["scout-2"].status == "rtb"
    # Verify scout-1 was forced to HOLD
    assert belief.agents["scout-1"].status == "holding"

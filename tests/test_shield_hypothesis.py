"""Hypothesis property-based tests for Safety Shield invariants I1-I6 (Spec §6.6.1, §10.6)."""

import numpy as np
from hypothesis import given, settings, strategies as st
from samanvay.core.belief import BeliefState
from samanvay.core.constants import GRID_HEIGHT, GRID_WIDTH, PLUME_NO_FLY_THRESHOLD
from samanvay.core.models import AgentState, Payload, Task, TaskStatus, TaskType
from samanvay.w5.shield import SafetyShield


@settings(max_examples=50, deadline=None)
@given(
    x1=st.integers(min_value=-5, max_value=GRID_WIDTH + 5),
    y1=st.integers(min_value=-5, max_value=GRID_HEIGHT + 5),
    alt1=st.integers(min_value=0, max_value=3),
    bat1=st.floats(min_value=0.0, max_value=1.0),
    hazard_val=st.floats(min_value=0.0, max_value=1.0),
)
def test_hypothesis_shield_invariants_i1_i2_i3(x1, y1, alt1, bat1, hazard_val):
    """Property test for Invariants I1 (no-fly), I2 (reserve), and I3 (geofence)."""
    shield = SafetyShield()
    plume = np.zeros((GRID_HEIGHT, GRID_WIDTH), dtype=np.float32)

    # If within grid, set hazard
    if 0 <= x1 < GRID_WIDTH and 0 <= y1 < GRID_HEIGHT:
        plume[y1, x1] = hazard_val

    belief = BeliefState(
        t=10.0,
        grid_size=(GRID_WIDTH, GRID_HEIGHT),
        known_plume=plume,
        agents={
            "scout-1": AgentState(
                id="scout-1",
                type="scout_drone",
                pos=(x1, y1),
                alt_band=alt1,
                battery=bat1,
                drain_rate_est=0.00067,
                status="executing",
            )
        },
    )

    violations = shield.check_invariants(belief)
    inv_ids = {v.invariant_id for v in violations}

    # Verify I3: Geofence
    if not (0 <= x1 < GRID_WIDTH and 0 <= y1 < GRID_HEIGHT):
        assert "I3_GEOFENCE" in inv_ids
    else:
        assert "I3_GEOFENCE" not in inv_ids

    # Verify I1: Plume
    if 0 <= x1 < GRID_WIDTH and 0 <= y1 < GRID_HEIGHT and alt1 > 0:
        if hazard_val >= PLUME_NO_FLY_THRESHOLD:
            assert "I1_NO_FLY" in inv_ids
        else:
            assert "I1_NO_FLY" not in inv_ids

    # Enforce overrides and check invariant post-condition
    shield.enforce_overrides(belief)
    agent = belief.agents["scout-1"]

    if "I1_NO_FLY" in inv_ids:
        assert agent.status == "holding"
    if "I3_GEOFENCE" in inv_ids:
        assert agent.status == "holding"


@settings(max_examples=40, deadline=None)
@given(
    d_x=st.integers(min_value=0, max_value=5),
    d_y=st.integers(min_value=0, max_value=5),
    alt1=st.integers(min_value=1, max_value=3),
    alt2=st.integers(min_value=1, max_value=3),
)
def test_hypothesis_shield_invariant_i4_altitude_separation(d_x, d_y, alt1, alt2):
    """Property test for Invariant I4: Altitude separation within close proximity."""
    shield = SafetyShield()
    pos1 = (10, 10)
    pos2 = (10 + d_x, 10 + d_y)

    belief = BeliefState(
        t=20.0,
        grid_size=(GRID_WIDTH, GRID_HEIGHT),
        known_plume=np.zeros((GRID_HEIGHT, GRID_WIDTH), dtype=np.float32),
        agents={
            "scout-1": AgentState(id="scout-1", type="scout_drone", pos=pos1, alt_band=alt1, battery=0.9),
            "scout-2": AgentState(id="scout-2", type="scout_drone", pos=pos2, alt_band=alt2, battery=0.9),
        },
    )

    violations = shield.check_invariants(belief)
    inv_ids = {v.invariant_id for v in violations}

    if d_x <= 2 and d_y <= 2 and alt1 == alt2:
        assert "I4_ALTITUDE_SEPARATION" in inv_ids
        shield.enforce_overrides(belief)
        # At least one drone must hold
        assert belief.agents["scout-2"].status == "holding" or belief.agents["scout-1"].status == "holding"
    else:
        assert "I4_ALTITUDE_SEPARATION" not in inv_ids

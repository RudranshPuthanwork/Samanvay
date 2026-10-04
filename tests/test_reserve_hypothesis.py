"""Hypothesis property tests for dynamic battery reserve monotonicity (Spec §6.4.2)."""

from hypothesis import given, settings, strategies as st
from samanvay.core.models import AgentState, Payload
from samanvay.core.reserve import compute_required_reserve


@settings(max_examples=50, deadline=None)
@given(
    d1=st.integers(min_value=0, max_value=30),
    d2=st.integers(min_value=31, max_value=60),
    agent_type=st.sampled_from(["scout_drone", "cargo_drone", "ground_rover", "relay_drone"]),
)
def test_hypothesis_reserve_monotonicity_distance(d1, d2, agent_type):
    """Dynamic battery reserve must be non-decreasing with increasing distance from base."""
    base = (2, 2)
    # Agent 1 at (2 + d1, 2)
    ag1 = AgentState(
        id="test-1",
        type=agent_type,
        pos=(base[0] + d1, base[1]),
        battery=1.0,
    )
    # Agent 2 at (2 + d2, 2)
    ag2 = AgentState(
        id="test-2",
        type=agent_type,
        pos=(base[0] + d2, base[1]),
        battery=1.0,
    )

    r1 = compute_required_reserve(ag1, base_pos=base)
    r2 = compute_required_reserve(ag2, base_pos=base)

    assert r2 >= r1, f"Reserve for d2={d2} ({r2}) must be >= reserve for d1={d1} ({r1})"


@settings(max_examples=40, deadline=None)
@given(
    load1=st.integers(min_value=0, max_value=1),
    load2=st.integers(min_value=2, max_value=4),
)
def test_hypothesis_reserve_monotonicity_payload(load1, load2):
    """Reserve required must be non-decreasing with heavier payload."""
    base = (2, 2)
    ag1 = AgentState(
        id="rover-1",
        type="ground_rover",
        pos=(15, 15),
        payload=Payload(capacity=4, carrying=["medkit"] * load1),
        battery=1.0,
    )
    ag2 = AgentState(
        id="rover-2",
        type="ground_rover",
        pos=(15, 15),
        payload=Payload(capacity=4, carrying=["medkit"] * load2),
        battery=1.0,
    )

    r1 = compute_required_reserve(ag1, base_pos=base)
    r2 = compute_required_reserve(ag2, base_pos=base)

    assert r2 >= r1, f"Reserve for payload {load2} ({r2}) must be >= reserve for payload {load1} ({r1})"

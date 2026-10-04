"""SAMANVAY system constants, default policies, assumptions, and estimates.

Conventions from SAMANVAY_EL05_Architecture_v2_0.md:
- [ASSUMPTION]: Believed parameters, tunable per scenario
- [ESTIMATE]: Performance and computational budgets
- [POLICY]: Operator-set parameters that dictate autonomy trade-offs
- [TARGET]: Quality and performance goals
"""

from typing import Final

# Map & Grid Geometry
GRID_WIDTH: Final[int] = 64
GRID_HEIGHT: Final[int] = 48
CELL_METERS: Final[float] = 10.0  # 640m x 480m area

# Triage & ESA (Expected Survival-Weighted Aid) [POLICY defaults]
# Weights w for urgency classes: critical, serious, stable
TRIAGE_WEIGHTS: Final[dict[str, float]] = {
    "critical": 3.0,
    "serious": 2.0,
    "stable": 1.0,
}
# Survival half-lives/time constants tau (in seconds): 20 min, 60 min, 180 min
TRIAGE_TAU_S: Final[dict[str, float]] = {
    "critical": 20.0 * 60.0,   # 1200 s
    "serious": 60.0 * 60.0,    # 3600 s
    "stable": 180.0 * 60.0,    # 10800 s
}
# Typical verify-and-deliver delay delta (seconds) [ASSUMPTION]
DEFAULT_VERIFY_DELIVER_DELAY_S: Final[float] = 180.0

# Base Station
BASE_COORDINATES: Final[tuple[int, int]] = (2, 2)
BASE_RADIO_RANGE_M: Final[float] = 400.0

# Base Staging Pads - ensures all 5 agents are visible at distinct starting slots
BASE_STAGING_PADS: Final[dict[str, tuple[float, float]]] = {
    "scout-1": (1.0, 2.0),
    "scout-2": (2.0, 1.0),
    "cargo-1": (2.0, 3.0),
    "rover-1": (3.0, 2.0),
    "relay-1": (3.0, 3.0),
}

# Radio / Comms [ASSUMPTION]
DEFAULT_PACKET_BUDGET_PER_TICK: Final[int] = 4
LEASE_DURATION_S: Final[float] = 120.0  # Lease validity window when disconnected

# Foresight Rollout Engine [TARGET / ESTIMATE]
FORESIGHT_N_ROLLOUTS: Final[int] = 64
FORESIGHT_HORIZON_S: Final[float] = 600.0
FORESIGHT_DT_S: Final[float] = 5.0
FORESIGHT_BOOTSTRAP_ROUNDS: Final[int] = 200

# Safety Shield Invariants [POLICY]
MIN_RESERVE_BATTERY_RATIO: Final[float] = 0.15  # Minimum reserve fraction
PLUME_NO_FLY_THRESHOLD: Final[float] = 0.5     # Plume concentration >= 0.5 is no-fly
MAX_ALTITUDE_BAND: Final[int] = 3

# Simulation Clock
SIM_DT_S: Final[float] = 1.0

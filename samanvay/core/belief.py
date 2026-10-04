"""Belief state for SAMANVAY planners, Foresight, and UI (Spec §5.1, §6.3.4).

The belief state is what the swarm knows. It is updated by incoming sensor observations
and radio telemetry, and never accesses ground-truth hidden state directly.
"""

from dataclasses import dataclass, field
import numpy as np

from samanvay.core.models import AgentState, Task


@dataclass
class DetectionBelief:
    id: str
    cell: tuple[int, int]
    posterior: float
    confirmed_urgency: str | None = None  # "critical", "serious", "stable"
    status: str = "unverified"  # "unverified", "confirmed", "false_alarm", "aided"
    first_detected_t: float = 0.0


@dataclass
class BeliefState:
    """Belief state maintained by the mission brain."""
    t: float = 0.0
    grid_size: tuple[int, int] = (64, 48)

    # Observed terrain (e.g. road confirmed blocked with rubble)
    observed_terrain: list[list[str]] = field(default_factory=list)

    # Bayesian search map: P(cell contains survivor)
    # Shape is (height=48, width=64)
    search_prior: np.ndarray = field(
        default_factory=lambda: np.zeros((48, 64), dtype=np.float32)
    )

    # Known / estimated hazard plume (0.0 to 1.0)
    known_plume: np.ndarray = field(
        default_factory=lambda: np.zeros((48, 64), dtype=np.float32)
    )

    # Estimated agent states (last heard pos, battery estimate, leases)
    agents: dict[str, AgentState] = field(default_factory=dict)

    # Detections
    detections: dict[str, DetectionBelief] = field(default_factory=dict)

    # Known radio links (agent_id, other_id)
    radio_edges: list[tuple[str, str]] = field(default_factory=list)

    # Active tasks
    tasks: dict[str, Task] = field(default_factory=dict)

    def get_search_prob(self, x: int, y: int) -> float:
        """Get search probability at grid cell (x, y)."""
        if 0 <= x < self.grid_size[0] and 0 <= y < self.grid_size[1]:
            return float(self.search_prior[y, x])
        return 0.0

    def update_bayesian_cell(
        self,
        x: int,
        y: int,
        detected: bool,
        p_detect: float,
        p_false_alarm: float,
    ) -> float:
        """Apply Stone (1975) Bayesian update to cell (x, y).

        P(S | D) = P(D | S) P(S) / [P(D | S) P(S) + P(D | ~S) P(~S)]
        where:
        - If detected: P(D | S) = p_detect, P(D | ~S) = p_false_alarm
        - If NOT detected: P(~D | S) = 1 - p_detect, P(~D | ~S) = 1 - p_false_alarm
        """
        if not (0 <= x < self.grid_size[0] and 0 <= y < self.grid_size[1]):
            return 0.0

        p_prior = float(self.search_prior[y, x])
        if detected:
            p_evidence_given_s = p_detect
            p_evidence_given_not_s = p_false_alarm
        else:
            p_evidence_given_s = 1.0 - p_detect
            p_evidence_given_not_s = 1.0 - p_false_alarm

        numerator = p_evidence_given_s * p_prior
        denominator = numerator + (p_evidence_given_not_s * (1.0 - p_prior))

        if denominator > 1e-9:
            p_post = float(numerator / denominator)
        else:
            p_post = 0.0

        self.search_prior[y, x] = np.clip(p_post, 0.0, 1.0)
        return float(self.search_prior[y, x])

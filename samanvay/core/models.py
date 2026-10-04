"""Frozen inter-module schema definitions for SAMANVAY v2.0 (Spec §5.3).

All models validate with Pydantic v2 and represent serializable contracts
across Python workstreams, the WebSocket connection, and the storage layer.
"""

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------

class EventOrigin(str, Enum):
    SIMULATED = "simulated"
    SCHEDULED = "scheduled"
    OPERATOR_INJECTED = "operator_injected"
    JUDGE_INJECTED = "judge_injected"


class EventType(str, Enum):
    DETECTION = "DETECTION"
    AFTERSHOCK = "AFTERSHOCK"
    COMMS_LOSS = "COMMS_LOSS"
    COMMS_RESTORED = "COMMS_RESTORED"
    WEATHER_CHANGE = "WEATHER_CHANGE"
    BATTERY_FAULT = "BATTERY_FAULT"
    AGENT_FAILURE = "AGENT_FAILURE"
    LEASE_EXPIRED = "LEASE_EXPIRED"
    SURVIVOR_AIDED = "SURVIVOR_AIDED"


class PriorityClass(str, Enum):
    P1 = "P1"  # Committed rescue on verified survivor
    P2 = "P2"  # Verification of a detection
    P3 = "P3"  # Systematic search


class TaskType(str, Enum):
    SEARCH = "SEARCH"
    VERIFY = "VERIFY"
    DELIVER = "DELIVER"
    RELAY = "RELAY"
    RTB = "RTB"
    HOLD = "HOLD"


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    EXECUTING = "executing"
    COMPLETED = "completed"
    SHED = "shed"
    FAILED = "failed"


class DecisionKind(str, Enum):
    ASSIGN = "ASSIGN"
    REASSIGN = "REASSIGN"
    REROUTE = "REROUTE"
    RELAY_MOVE = "RELAY_MOVE"
    SHED = "SHED"
    SWITCH_PLAN = "SWITCH_PLAN"
    ESCALATE = "ESCALATE"
    SHIELD_OVERRIDE = "SHIELD_OVERRIDE"
    LEASE_EXPIRE = "LEASE_EXPIRE"
    TASK_CLOSED = "TASK_CLOSED"
    DISPATCH = "DISPATCH"
    SHIELD_REFUSAL = "SHIELD_REFUSAL"
    POLICY_CHOICE = "POLICY_CHOICE"


class DecisionClassification(str, Enum):
    FACT = "FACT"
    VALUE = "VALUE"
    POLICY = "POLICY"
    SAFETY = "SAFETY"


# -----------------------------------------------------------------------------
# 5.3.1 ScenarioManifest
# -----------------------------------------------------------------------------

class MapManifest(BaseModel):
    model_config = ConfigDict(frozen=True)
    source: Literal["osm", "synthetic"]
    grid: tuple[int, int] = (64, 48)
    cell_m: float = 10.0
    origin_latlon: tuple[float, float] = (19.1075, 72.8370)
    attribution: str = "© OpenStreetMap contributors (ODbL)"


class QuakeManifest(BaseModel):
    model_config = ConfigDict(frozen=True)
    epicentre_cell: tuple[int, int]
    intensity_decay_cells: float = 30.0


class SurvivorManifest(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    cell: tuple[int, int]
    urgency: Literal["critical", "serious", "stable"]


class PlumeManifest(BaseModel):
    model_config = ConfigDict(frozen=True)
    source_cell: tuple[int, int]
    growth_cells_per_min: float = 0.6
    wind_deg: float = 225.0
    wind_mps: float = 4.0


class ScheduledEventManifest(BaseModel):
    model_config = ConfigDict(frozen=True)
    t: float
    type: EventType
    cells: list[tuple[int, int]] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)


class ScenarioManifest(BaseModel):
    model_config = ConfigDict(frozen=True)
    scenario_id: str
    family: Literal["F1", "F2", "F3", "F4"]
    seed: int
    map: MapManifest
    quake: QuakeManifest
    survivors: list[SurvivorManifest]
    plume: PlumeManifest
    scheduled_events: list[ScheduledEventManifest] = Field(default_factory=list)
    agents: list[str] = Field(
        default_factory=lambda: ["scout-1", "scout-2", "cargo-1", "rover-1", "relay-1"]
    )


# -----------------------------------------------------------------------------
# 5.3.2 AgentState
# -----------------------------------------------------------------------------

class Lease(BaseModel):
    model_config = ConfigDict(frozen=True)
    task: str
    expires_t: float


class Payload(BaseModel):
    model_config = ConfigDict(frozen=True)
    capacity: int = 0
    carrying: list[str] = Field(default_factory=list)


class AgentState(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    type: str  # e.g., "scout_drone", "cargo_drone", "ground_rover", "relay_drone"
    pos: tuple[int, int]
    alt_band: int = 0  # 0 for ground, 1-3 for air
    battery: float = 1.0  # 0.0 to 1.0
    drain_rate_est: float = 0.0007
    reserve_required: float = 0.15
    status: Literal["idle", "executing", "holding", "rtb", "lost", "failed"] = "idle"
    connected: bool = True
    last_heard_t: float = 0.0
    lease: Lease | None = None
    payload: Payload = Field(default_factory=Payload)
    route: list[tuple[int, int]] = Field(default_factory=list)
    ghost_route: list[tuple[int, int]] = Field(default_factory=list)
    queue: list[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# 5.3.3 Task
# -----------------------------------------------------------------------------

class ValueModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    urgency: Literal["critical", "serious", "stable"] = "stable"
    p_real: float = 0.5


class Task(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    type: TaskType
    priority_class: PriorityClass
    asr_phase: int = 1
    location: tuple[int, int]
    requires: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    value_model: ValueModel = Field(default_factory=ValueModel)
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: str | None = None
    created_by: str = "initial"
    shed: bool = False


# -----------------------------------------------------------------------------
# 5.3.4 Event
# -----------------------------------------------------------------------------

class Event(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    t: float
    type: EventType
    source: str = "system"
    data: dict[str, Any] = Field(default_factory=dict)
    origin: EventOrigin = EventOrigin.SIMULATED


# -----------------------------------------------------------------------------
# 5.3.5 Forecast (W4 Foresight)
# -----------------------------------------------------------------------------

class ForecastCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)
    plan_id: str
    esa_mean: float
    esa_ci95: tuple[float, float]
    p_agent_loss: float
    p_p1_fail: float
    tti_s: float | None = None


class PairedDelta(BaseModel):
    model_config = ConfigDict(frozen=True)
    a: str
    b: str
    d_esa_ci95: tuple[float, float]
    d_ploss_ci95: tuple[float, float]


class Forecast(BaseModel):
    model_config = ConfigDict(frozen=True)
    epoch: int
    t: float
    n_rollouts: int = 64
    horizon_s: float = 600.0
    crn_seed: int
    candidates: list[ForecastCandidate]
    paired_deltas: list[PairedDelta] = Field(default_factory=list)
    classification: DecisionClassification
    reason: str


# -----------------------------------------------------------------------------
# 5.3.6 DecisionRecord
# -----------------------------------------------------------------------------

class OperatorChoice(BaseModel):
    model_config = ConfigDict(frozen=True)
    option: str
    t: float
    operator: str = "op-1"


class DecisionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    t: float
    kind: DecisionKind
    classification: DecisionClassification
    trigger_event: int | None = None
    forecast_epoch: int | None = None
    chosen: str | None = None
    options: list[str] = Field(default_factory=list)
    operator_choice: OperatorChoice | None = None
    explanation: str
    prev_hash: str
    hash: str


# -----------------------------------------------------------------------------
# 5.3.7 MissionSpec (DSL from W1)
# -----------------------------------------------------------------------------

class MissionPhase(BaseModel):
    model_config = ConfigDict(frozen=True)
    asr: int  # 1, 2, or 3
    area: str | None = None
    sectors: list[str] = Field(default_factory=list)
    goal: str | None = None
    priority: int = 1
    trigger: str | None = None
    spawn: list[str] = Field(default_factory=list)


class Constraint(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["comms", "avoid", "geofence", "time"]
    rule: str | None = None
    hazard: str | None = None
    max_duration_s: float | None = None


class PolicyConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_p_agent_loss: float | None = None
    p1_fail_floor: float = 0.30
    exchange_rate_agent_loss_vs_esa: float | None = None


class MissionSpec(BaseModel):
    model_config = ConfigDict(frozen=True)
    phases: list[MissionPhase]
    constraints: list[Constraint] = Field(default_factory=list)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)


# -----------------------------------------------------------------------------
# 5.3.8 WebSocket Messages
# -----------------------------------------------------------------------------

class WSMessage(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: str


class SnapshotPayload(BaseModel):
    model_config = ConfigDict(frozen=True)
    scenario_id: str
    t: float
    grid_size: tuple[int, int]
    terrain: list[list[str]]
    agents: dict[str, AgentState]
    tasks: dict[str, Task]
    plume: list[list[float]]
    belief_heatmap: list[list[float]]
    detections: list[dict[str, Any]]
    radio_edges: list[tuple[str, str]]


class SnapshotMessage(WSMessage):
    type: Literal["SNAPSHOT"] = "SNAPSHOT"
    payload: SnapshotPayload


class KPIData(BaseModel):
    model_config = ConfigDict(frozen=True)
    expected_aid: float
    survivors_aided: int
    p1_at_risk: int
    tti_s: float | None
    escalations_per_hour: float
    agents_lost: int


class TickPayload(BaseModel):
    model_config = ConfigDict(frozen=True)
    t: float
    agents: dict[str, AgentState]
    tasks: dict[str, Task]
    kpis: KPIData
    plume: list[list[float]] | None = None
    belief_heatmap: list[list[float]] | None = None
    terrain: list[list[str]] | None = None
    wind: dict[str, float] | None = None
    radio_edges: list[tuple[str, str]]
    detections: list[dict[str, Any]]
    events_this_tick: list[Event] = Field(default_factory=list)


class TickMessage(WSMessage):
    type: Literal["TICK"] = "TICK"
    payload: TickPayload


class ForecastMessage(WSMessage):
    type: Literal["FORECAST"] = "FORECAST"
    payload: Forecast


class DecisionMessage(WSMessage):
    type: Literal["DECISION"] = "DECISION"
    payload: DecisionRecord


class EscalationOption(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    title: str
    tradeoff_summary: str
    esa_ci95: tuple[float, float]
    p_agent_loss: float
    p_p1_fail: float
    is_default: bool = False


class EscalationPayload(BaseModel):
    model_config = ConfigDict(frozen=True)
    escalation_id: int
    trigger_reason: str
    deadline_s: float
    default_option_id: str
    options: list[EscalationOption]


class EscalationMessage(WSMessage):
    type: Literal["ESCALATION"] = "ESCALATION"
    payload: EscalationPayload


class CommsQueueItem(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    recipient: str
    type: str
    voi_score: float
    sent: bool = False


class CommsPayload(BaseModel):
    model_config = ConfigDict(frozen=True)
    t: float
    budget_remaining: int
    queue: list[CommsQueueItem]
    sent_this_tick: list[str]


class CommsMessage(WSMessage):
    type: Literal["COMMS"] = "COMMS"
    payload: CommsPayload

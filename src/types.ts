export interface AgentState {
  id: string;
  type: string;
  pos: [number, number];
  alt_band: number;
  battery: number;
  drain_rate_est: number;
  reserve_required: number;
  status: "idle" | "executing" | "holding" | "rtb" | "lost" | "failed";
  connected: boolean;
  last_heard_t: number;
  lease?: { task: string; expires_t: number };
  payload: { capacity: number; carrying: string[] };
  route: [number, number][];
  ghost_route?: [number, number][];
  queue: string[];
}

export interface Task {
  id: string;
  type: string;
  priority_class: "P1" | "P2" | "P3";
  asr_phase: number;
  location: [number, number];
  requires: string[];
  depends_on: string[];
  value_model: { urgency: string; p_real: number };
  status: string;
  assigned_to?: string;
  created_by: string;
  shed: boolean;
}

export interface KPIData {
  expected_aid: number;
  survivors_aided: number;
  p1_at_risk: number;
  tti_s?: number | null;
  escalations_per_hour: number;
  agents_lost: number;
}

export interface DetectionItem {
  id: string;
  cell: [number, number];
  posterior: number;
  urgency?: string | null;
  status: string;
}

export interface DecisionRecord {
  id: number;
  t: number;
  kind: "ASSIGN" | "REASSIGN" | "REROUTE" | "RELAY_MOVE" | "SHED" | "SWITCH_PLAN" | "ESCALATE" | "SHIELD_OVERRIDE" | "LEASE_EXPIRE" | "TASK_CLOSED" | "DISPATCH" | "SHIELD_REFUSAL" | "POLICY_CHOICE";
  classification: "FACT" | "VALUE" | "POLICY" | "SAFETY";
  trigger_event?: number | null;
  forecast_epoch?: number | null;
  chosen?: string | null;
  options: string[];
  explanation: string;
  prev_hash: string;
  hash: string;
}

export interface ForecastCandidate {
  plan_id: string;
  esa_mean: number;
  esa_ci95: [number, number];
  p_agent_loss: number;
  p_p1_fail: number;
  tti_s?: number | null;
}

export interface Forecast {
  epoch: number;
  t: number;
  n_rollouts: number;
  horizon_s: number;
  crn_seed: number;
  candidates: ForecastCandidate[];
  paired_deltas: { a: string; b: string; d_esa_ci95: [number, number]; d_ploss_ci95: [number, number] }[];
  classification: "FACT" | "VALUE" | "POLICY" | "SAFETY";
  reason: string;
}

export interface EscalationOption {
  id: string;
  title: string;
  tradeoff_summary: string;
  esa_ci95: [number, number];
  p_agent_loss: number;
  p_p1_fail: number;
  is_default: boolean;
}

export interface EscalationPayload {
  escalation_id: number;
  trigger_reason: string;
  deadline_s: number;
  default_option_id: string;
  options: EscalationOption[];
}

export interface CommsQueueItem {
  id: string;
  recipient: string;
  type: string;
  voi_score: number;
  sent: boolean;
}

export interface CommsPayload {
  t: number;
  budget_remaining: number;
  queue: CommsQueueItem[];
  sent_this_tick: string[];
}

import React, { useEffect, useRef, useState } from "react";
import { Header } from "./components/Header";
import { KPILine } from "./components/KPILine";
import { MissionMap } from "./components/MissionMap";
import { AgentRoster } from "./components/AgentRoster";
import { ForesightFanChart } from "./components/ForesightFanChart";
import { DecisionLog } from "./components/DecisionLog";
import { CommsQueueView } from "./components/CommsQueueView";
import { EventInjectionRow } from "./components/EventInjectionRow";
import { CommandLine } from "./components/CommandLine";
import { EscalationModal } from "./components/EscalationModal";
import { BriefStage, PolicySettings } from "./components/BriefStage";
import { ReviewStage } from "./components/ReviewStage";
import {
  AgentState,
  CommsPayload,
  DecisionRecord,
  DetectionItem,
  EscalationPayload,
  Forecast,
  KPIData,
  Task,
} from "./types";

interface HistoryTick {
  t: number;
  agents: Record<string, AgentState>;
  tasks: Record<string, Task>;
  plume: number[][];
  beliefHeatmap: number[][];
  detections: DetectionItem[];
  radioEdges: [string, string][];
  kpis: KPIData;
}

const INITIAL_AGENTS: Record<string, AgentState> = {
  S1: { id: "S1", type: "uav_scout", alt_band: 1, pos: [10, 10], battery: 98, drain_rate_est: 0.1, reserve_required: 15, status: "idle", connected: true, last_heard_t: 0, payload: { capacity: 1, carrying: [] }, route: [], queue: [] },
  S2: { id: "S2", type: "uav_scout", alt_band: 1, pos: [50, 10], battery: 96, drain_rate_est: 0.1, reserve_required: 15, status: "idle", connected: true, last_heard_t: 0, payload: { capacity: 1, carrying: [] }, route: [], queue: [] },
  D1: { id: "D1", type: "uav_cargo", alt_band: 2, pos: [20, 20], battery: 100, drain_rate_est: 0.15, reserve_required: 20, status: "idle", connected: true, last_heard_t: 0, payload: { capacity: 2, carrying: ["medkit", "medkit"] }, route: [], queue: [] },
  D2: { id: "D2", type: "uav_cargo", alt_band: 2, pos: [40, 20], battery: 100, drain_rate_est: 0.15, reserve_required: 20, status: "idle", connected: true, last_heard_t: 0, payload: { capacity: 2, carrying: ["medkit", "medkit"] }, route: [], queue: [] },
  R1: { id: "R1", type: "ugv_rover", alt_band: 0, pos: [14, 8], battery: 100, drain_rate_est: 0.05, reserve_required: 10, status: "idle", connected: true, last_heard_t: 0, payload: { capacity: 4, carrying: ["heavy_gear"] }, route: [], queue: [] },
};

export const App: React.FC = () => {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const urlParams = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
  const initialStage = (urlParams?.get("stage") as "brief" | "operate" | "review") || "brief";
  const [activeStage, setActiveStage] = useState<"brief" | "operate" | "review">(initialStage);
  const [missionConfirmed, setMissionConfirmed] = useState(initialStage === "operate" || initialStage === "review");
  const [judgeMode, setJudgeMode] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [speed, setSpeed] = useState(1);

  const [scenarioId, setScenarioId] = useState("VileParle_W_001");
  const [seed, setSeed] = useState(42);
  const [simTime, setSimTime] = useState(0);
  const [gridSize, setGridSize] = useState<[number, number]>([64, 48]);
  const [terrain, setTerrain] = useState<string[][]>([]);
  const [plume, setPlume] = useState<number[][]>([]);
  const [beliefHeatmap, setBeliefHeatmap] = useState<number[][]>([]);
  const [wind, setWind] = useState<{ deg: number; mps: number }>({ deg: 225, mps: 4.5 });

  const [agents, setAgents] = useState<Record<string, AgentState>>(INITIAL_AGENTS);
  const [, setTasks] = useState<Record<string, Task>>({});
  const [detections, setDetections] = useState<DetectionItem[]>([]);
  const [radioEdges, setRadioEdges] = useState<[string, string][]>([]);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [decisions, setDecisions] = useState<DecisionRecord[]>([]);
  const [activeEscalation, setActiveEscalation] = useState<EscalationPayload | null>(null);
  const [comms, setComms] = useState<CommsPayload>({ t: 0, budget_remaining: 100, queue: [], sent_this_tick: [] });
  const [kpis, setKpis] = useState<KPIData>({
    expected_aid: 0,
    survivors_aided: 0,
    p1_at_risk: 0,
    tti_s: null,
    escalations_per_hour: 0,
    agents_lost: 0,
  });

  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [selectedRecordId, setSelectedRecordId] = useState<number | null>(null);
  const [focusTargetCell, setFocusTargetCell] = useState<[number, number] | null>(null);
  const [previewPlanRoutes, setPreviewPlanRoutes] = useState<[number, number][][] | null>(null);
  const [lastMission, setLastMission] = useState<string | null>(null);

  // Time scrubber state for Operate review (last 5 minutes)
  const historyTicksRef = useRef<HistoryTick[]>([]);
  const [scrubIndex, setScrubIndex] = useState<number | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const plumeRef = useRef(plume);
  const beliefHeatmapRef = useRef(beliefHeatmap);
  useEffect(() => {
    plumeRef.current = plume;
  }, [plume]);
  useEffect(() => {
    beliefHeatmapRef.current = beliefHeatmap;
  }, [beliefHeatmap]);

  // Connect to backend WebSocket at 127.0.0.1:8000
  useEffect(() => {
    let disposed = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      const ws = new WebSocket("ws://127.0.0.1:8000/ws");
      wsRef.current = ws;

      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => {
        setWsConnected(false);
        if (!disposed) retryTimer = setTimeout(connect, 1500);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "SNAPSHOT") {
            const p = msg.payload;
            setScenarioId(p.scenario_id);
            setSimTime(p.t);
            setGridSize(p.grid_size);
            setTerrain(p.terrain);
            setAgents(p.agents);
            setTasks(p.tasks);
            setPlume(p.plume);
            setBeliefHeatmap(p.belief_heatmap);
            setDetections(p.detections);
            setRadioEdges(p.radio_edges);
            setDecisions([]);
            historyTicksRef.current = [];
            setScrubIndex(null);
          } else if (msg.type === "TICK") {
            const p = msg.payload;
            setSimTime(p.t);
            setAgents(p.agents);
            setTasks(p.tasks);
            setKpis(p.kpis);
            if (p.terrain) setTerrain(p.terrain);
            if (p.wind) setWind(p.wind);
            if (p.plume) setPlume(p.plume);
            if (p.belief_heatmap) setBeliefHeatmap(p.belief_heatmap);
            setRadioEdges(p.radio_edges);
            setDetections(p.detections);

            // Record to time scrubber history ring buffer (last 300s = 5 min)
            historyTicksRef.current.push({
              t: p.t,
              agents: p.agents,
              tasks: p.tasks,
              plume: p.plume || plumeRef.current,
              beliefHeatmap: p.belief_heatmap || beliefHeatmapRef.current,
              detections: p.detections,
              radioEdges: p.radio_edges,
              kpis: p.kpis,
            });
            const minT = p.t - 300;
            while (historyTicksRef.current.length > 1 && historyTicksRef.current[0] && historyTicksRef.current[0].t < minT) {
              historyTicksRef.current.shift();
            }
          } else if (msg.type === "FORECAST") {
            setForecast(msg.payload);
          } else if (msg.type === "DECISION") {
            setDecisions((prev) => [...prev, msg.payload]);
          } else if (msg.type === "ESCALATION") {
            setActiveEscalation(msg.payload);
          } else if (msg.type === "COMMS") {
            setComms(msg.payload);
          }
        } catch {
          // Ignore unparseable frames
        }
      };
    };

    connect();

    return () => {
      disposed = true;
      clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, []);

  /** Send a message to the server */
  const send = (msg: Record<string, unknown>): boolean => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn("[samanvay] WebSocket not connected; dropped message", msg);
      return false;
    }
    ws.send(JSON.stringify(msg));
    return true;
  };

  const handleTogglePlay = () => {
    const next = !isRunning;
    setIsRunning(next);
    if (next) {
      // Resuming live
      setScrubIndex(null);
    }
    send({ type: "SIM_CONTROL", action: next ? "play" : "pause" });
  };

  const handleSetSpeed = (s: number) => {
    setSpeed(s);
    send({ type: "SIM_CONTROL", action: "speed", speed: s });
  };

  const handleMissionSubmit = (text: string) => {
    setLastMission(text);
    setMissionConfirmed(true);
    setIsRunning(true);
    setScrubIndex(null);
    send({ type: "MISSION_SUBMIT", objective: text });
  };

  const handlePolicyPresetChange = (preset: "cautious" | "balanced" | "aggressive") => {
    send({
      type: "POLICY_SET",
      preset,
    });
  };

  const handleLaunchMissionFromBrief = (text: string, policy: PolicySettings) => {
    send({
      type: "POLICY_SET",
      preset: policy.preset,
      policy,
    });
    handleMissionSubmit(text);
    setActiveStage("operate");
  };

  const handleInjectEvent = (
    eventType: string,
    params?: Record<string, unknown>
  ): void => {
    send({
      type: "INJECT_EVENT",
      event_type: eventType,
      origin: "operator_injected",
      params: params || {},
    });
  };

  const handleNoFlyPolygon = (polygon: [number, number][]) => {
    send({
      type: "SET_NO_FLY_POLYGON",
      polygon,
    });
  };

  const handleTaskOverride = (taskId: string, agentId: string) => {
    send({
      type: "TASK_OVERRIDE",
      task_id: taskId,
      agent_id: agentId,
    });
  };

  const handleHoverEscalationOption = (optionId: string | null) => {
    if (!optionId || !forecast?.candidates) {
      setPreviewPlanRoutes(null);
      return;
    }
    const cand = forecast.candidates.find((c) => c.plan_id === optionId);
    if (cand && (cand as any).routes) {
      setPreviewPlanRoutes(Object.values((cand as any).routes));
    } else {
      const routes = Object.values(agents)
        .map((ag) => ag.route)
        .filter((r): r is [number, number][] => Boolean(r && r.length > 0));
      setPreviewPlanRoutes(routes);
    }
  };

  const handleEscalationResponse = (chosenOption: string) => {
    setActiveEscalation(null);
    setPreviewPlanRoutes(null);
    send({ type: "ESCALATION_RESPONSE", chosen_option: chosenOption });
  };

  const handleSelectDecisionRecord = (rec: DecisionRecord) => {
    setSelectedRecordId(rec.id);
    for (const agId of Object.keys(agents)) {
      if (rec.explanation.includes(agId)) {
        setSelectedAgentId(agId);
        break;
      }
    }
    const match = rec.explanation.match(/\[(\d+),\s*(\d+)\]/) || rec.explanation.match(/\((\d+),\s*(\d+)\)/);
    if (match && match[1] && match[2]) {
      setFocusTargetCell([parseInt(match[1], 10), parseInt(match[2], 10)]);
    }
  };

  // Keyboard controls (Spec §5.11): Space to pause, 1-5 for speed, Esc to cancel
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) {
        return;
      }

      if (e.key === " " || e.code === "Space") {
        e.preventDefault();
        handleTogglePlay();
      } else if (e.key === "1") {
        handleSetSpeed(1);
      } else if (e.key === "2") {
        handleSetSpeed(2);
      } else if (e.key === "5") {
        handleSetSpeed(5);
      } else if (e.key === "Escape") {
        setSelectedAgentId(null);
        setSelectedRecordId(null);
        setFocusTargetCell(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isRunning, speed, selectedAgentId]);

  // Active or scrubbed state
  const isScrubbing = scrubIndex !== null && historyTicksRef.current[scrubIndex] !== undefined;
  const scrubbedTick = isScrubbing ? historyTicksRef.current[scrubIndex!] : null;

  const currentAgents = scrubbedTick ? scrubbedTick.agents : agents;
  const currentPlume = scrubbedTick ? scrubbedTick.plume : plume;
  const currentBelief = scrubbedTick ? scrubbedTick.beliefHeatmap : beliefHeatmap;
  const currentDetections = scrubbedTick ? scrubbedTick.detections : detections;
  const currentRadio = scrubbedTick ? scrubbedTick.radioEdges : radioEdges;
  const currentKpis = scrubbedTick ? scrubbedTick.kpis : kpis;
  const currentSimTime = scrubbedTick ? scrubbedTick.t : simTime;
  const displayDecisions = scrubbedTick
    ? decisions.filter((d) => d.t <= scrubbedTick.t)
    : decisions;

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-ground text-ink select-none font-sans">
      {/* 40px Header with One-Line Stage Switch (Brief, Operate, Review) */}
      <Header
        scenarioId={scenarioId}
        seed={seed}
        simTime={currentSimTime}
        isRunning={isRunning}
        speed={speed}
        theme={theme}
        activeStage={activeStage}
        missionConfirmed={missionConfirmed}
        judgeMode={judgeMode}
        onSelectStage={setActiveStage}
        onTogglePlay={handleTogglePlay}
        onSetSpeed={handleSetSpeed}
        onToggleTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
        onToggleJudgeMode={() => setJudgeMode((j) => !j)}
      />

      {/* 32px KPI Line */}
      <KPILine kpis={currentKpis} />

      {/* Time Scrubber Bar when Paused in Operate (Spec §5.10) */}
      {activeStage === "operate" && !isRunning && historyTicksRef.current.length > 1 && (
        <div className="h-8 border-b border-rule bg-surface px-4 flex items-center justify-between text-xs font-mono">
          <div className="flex items-center space-x-3 text-ink-2">
            <span className="text-attention font-bold">PAUSED</span>
            <span className="text-ink-3">Review scrubber (last 5 min):</span>
            <input
              type="range"
              min={0}
              max={historyTicksRef.current.length - 1}
              value={scrubIndex !== null ? scrubIndex : historyTicksRef.current.length - 1}
              onChange={(e) => setScrubIndex(parseInt(e.target.value, 10))}
              className="w-72 accent-attention"
            />
            <span className="text-ink font-semibold tabular-nums">
              t = {currentSimTime.toFixed(1)}s ({displayDecisions.length} decisions)
            </span>
          </div>
          <button
            onClick={() => {
              setScrubIndex(null);
              handleTogglePlay();
            }}
            className="px-2 py-0.5 border border-rule hover:border-attention text-attention bg-surface-raised font-mono text-[11px]"
          >
            Resume live
          </button>
        </div>
      )}

      {/* Stage Views (Brief, Operate, Review) */}
      {activeStage === "brief" && (
        <BriefStage
          scenarioId={scenarioId}
          seed={seed}
          agents={agents}
          onLaunchMission={handleLaunchMissionFromBrief}
          onPolicyPresetChange={handlePolicyPresetChange}
          onSelectScenario={(fam, s) => {
            setScenarioId(`${fam}_s${s.toString().padStart(4, "0")}`);
            setSeed(s);
          }}
        />
      )}

      {activeStage === "operate" && (
        <>
          {/* Main Console Split: 68% map, 32% right zone */}
          <div className="flex-1 flex overflow-hidden min-h-0">
            {/* Left: Map (68% width) */}
            <div className="w-[68%] h-full">
              <MissionMap
                gridSize={gridSize}
                terrain={terrain}
                plume={currentPlume}
                beliefHeatmap={currentBelief}
                agents={currentAgents}
                detections={currentDetections}
                radioEdges={currentRadio}
                forecast={forecast}
                wind={wind}
                activeEscalation={Boolean(activeEscalation)}
                escalationTarget={
                  activeEscalation ? [38, 14] : null
                }
                selectedAgentId={selectedAgentId}
                onSelectAgent={setSelectedAgentId}
                onInjectEvent={handleInjectEvent}
                onNoFlyPolygon={handleNoFlyPolygon}
                onTaskOverride={handleTaskOverride}
                focusTargetCell={focusTargetCell}
                previewPlanRoutes={previewPlanRoutes}
              />
            </div>

            {/* Right: Vertical Stack (32% width) */}
            <div className="w-[32%] h-full flex flex-col bg-surface overflow-hidden border-l border-rule">
              <AgentRoster
                agents={currentAgents}
                selectedAgentId={selectedAgentId}
                onSelectAgent={setSelectedAgentId}
              />
              <ForesightFanChart forecast={forecast} />
              <DecisionLog
                records={displayDecisions}
                selectedRecordId={selectedRecordId}
                onSelectRecord={handleSelectDecisionRecord}
              />
              <CommsQueueView comms={comms} />
            </div>
          </div>

          {/* Bottom Controls */}
          <div className="flex flex-col">
            <EventInjectionRow
              onInject={handleInjectEvent}
              connected={wsConnected}
            />
            <CommandLine onSubmit={handleMissionSubmit} lastMission={lastMission} />
          </div>
        </>
      )}

      {activeStage === "review" && (
        <ReviewStage
          records={displayDecisions}
          simTime={currentSimTime}
        />
      )}

      {/* Escalation Modal */}
      {activeEscalation && (
        <EscalationModal
          escalation={activeEscalation}
          onSelectOption={handleEscalationResponse}
          onHoverOption={handleHoverEscalationOption}
        />
      )}
    </div>
  );
};

export default App;

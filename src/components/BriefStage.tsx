import React, { useState } from "react";
import { AgentState } from "../types";

interface BriefStageProps {
  scenarioId: string;
  seed: number;
  agents: Record<string, AgentState>;
  onLaunchMission: (objective: string, policy: PolicySettings) => void;
  onSelectScenario: (family: string, seed: number) => void;
  onPolicyPresetChange?: (preset: "cautious" | "balanced" | "aggressive") => void;
}

export interface PolicySettings {
  preset: "cautious" | "balanced" | "aggressive";
  agentLossLimit: number;
  p1Floor: number;
  p1Weight: number;
  p2Weight: number;
  p3Weight: number;
}

export const BriefStage: React.FC<BriefStageProps> = ({
  scenarioId,
  seed,
  agents: _agents,
  onLaunchMission,
  onSelectScenario,
  onPolicyPresetChange,
}) => {
  const [missionText, setMissionText] = useState(
    "Assess the whole area, then search sectors B and C, deliver medkits to anyone found, keep everyone in contact, avoid the smoke."
  );

  const [policy, setPolicy] = useState<PolicySettings>({
    preset: "balanced",
    agentLossLimit: 0.05,
    p1Floor: 0.8,
    p1Weight: 1.0,
    p2Weight: 0.5,
    p3Weight: 0.2,
  });

  const handleApplyPreset = (preset: "cautious" | "balanced" | "aggressive") => {
    onPolicyPresetChange?.(preset);
    if (preset === "cautious") {
      setPolicy({
        preset: "cautious",
        agentLossLimit: 0.0,
        p1Floor: 0.95,
        p1Weight: 1.2,
        p2Weight: 0.6,
        p3Weight: 0.2,
      });
    } else if (preset === "balanced") {
      setPolicy({
        preset: "balanced",
        agentLossLimit: 0.05,
        p1Floor: 0.8,
        p1Weight: 1.0,
        p2Weight: 0.5,
        p3Weight: 0.2,
      });
    } else {
      setPolicy({
        preset: "aggressive",
        agentLossLimit: 0.15,
        p1Floor: 0.65,
        p1Weight: 0.9,
        p2Weight: 0.4,
        p3Weight: 0.1,
      });
    }
  };

  // Agent capabilities table (Spec §6.2)
  const agentSpecs = [
    { id: "scout-1", type: "Air scout", sensor: "Search (r=20m, p=0.88)", speed: "12 m/s", payload: "None", comms: "120m" },
    { id: "scout-2", type: "Air scout", sensor: "Search (r=20m, p=0.88)", speed: "12 m/s", payload: "None", comms: "120m" },
    { id: "rover-1", type: "Ground rover", sensor: "Inspection (r=5m)", speed: "2.5 m/s", payload: "1 kit (ground)", comms: "80m" },
    { id: "cargo-1", type: "Cargo drone", sensor: "Navigation only", speed: "8 m/s", payload: "2 medkits (air)", comms: "100m" },
    { id: "relay-1", type: "Mesh relay", sensor: "Comms bridge only", speed: "10 m/s", payload: "Repeater", comms: "220m" },
  ];

  return (
    <div className="flex-1 flex overflow-hidden bg-ground text-ink select-none font-sans">
      {/* Left Column: District Context & Mission Confirmation (55% width) */}
      <div className="w-[55%] border-r border-rule p-5 flex flex-col space-y-4 overflow-y-auto">
        <div>
          <div className="text-xs text-ink-3 font-mono">Mission briefing · INSARAG methodology</div>
          <h1 className="text-lg font-medium text-ink mt-0.5">District operational brief</h1>
          <p className="text-xs text-ink-2 mt-1 leading-relaxed">
            Deployment zone: Vile Parle (West / East), Mumbai (640 × 480 m grid). High structural density with
            concentrated collapsed unreinforced masonry along SV Road corridors. Atmospheric drift carries chemical
            plume eastward from industrial perimeter.
          </p>
        </div>

        {/* Scenario & Seed Selection */}
        <div className="p-3 bg-surface border border-rule space-y-2">
          <div className="text-xs font-medium text-ink-2">Scenario profile</div>
          <div className="flex items-center space-x-3 text-xs font-mono">
            <button
              type="button"
              onClick={() => onSelectScenario("F1", seed)}
              className={`px-3 py-1 border ${
                scenarioId.startsWith("F1") ? "border-attention bg-surface-raised text-attention" : "border-rule text-ink-2"
              }`}
            >
              F1: Urban quake
            </button>
            <button
              type="button"
              onClick={() => onSelectScenario("F4", seed)}
              className={`px-3 py-1 border ${
                scenarioId.startsWith("F4") ? "border-attention bg-surface-raised text-attention" : "border-rule text-ink-2"
              }`}
            >
              F4: Night & degraded comms
            </button>
            <span className="text-ink-3">Seed:</span>
            {[42, 101, 777].map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => onSelectScenario(scenarioId.split("_")[0] || "F1", s)}
                className={`px-2 py-0.5 border ${
                  seed === s ? "border-ink text-ink font-medium" : "border-rule text-ink-3"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Typed Mission & Parsed INSARAG Phases */}
        <div className="p-3 bg-surface border border-rule space-y-2">
          <label htmlFor="mission-brief-input" className="text-xs font-medium text-ink-2">
            Mission objective (Natural language)
          </label>
          <textarea
            id="mission-brief-input"
            value={missionText}
            onChange={(e) => setMissionText(e.target.value)}
            rows={2}
            className="w-full bg-ground border border-rule p-2 text-xs font-mono text-ink focus:outline-none focus:border-attention"
          />

          <div className="text-xs font-medium text-ink-2 pt-1">Parsed operational phases:</div>
          <div className="space-y-1.5 text-xs font-mono text-ink-2">
            <div className="flex items-center space-x-2">
              <span className="text-ink-3 text-[11px] w-12 shrink-0">ASR 1</span>
              <span>Wide area reconnaissance (all sectors, priority cooling)</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="text-ink-3 text-[11px] w-12 shrink-0">ASR 2</span>
              <span>Sector assessment: targeted search on Sectors B & C</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="text-ink-3 text-[11px] w-12 shrink-0">ASR 3</span>
              <span>Search and rescue: rapid medkit delivery on verified detection</span>
            </div>
          </div>
        </div>

        {/* Launch Button */}
        <button
          type="button"
          onClick={() => onLaunchMission(missionText, policy)}
          className="w-full py-2 bg-surface-raised border border-rule-strong hover:border-attention text-ink font-medium text-xs transition-colors"
        >
          Confirm mission and launch swarm
        </button>
      </div>

      {/* Right Column: Commander Policy & Swarm Roster (45% width) */}
      <div className="w-[45%] p-5 flex flex-col space-y-4 overflow-y-auto">
        {/* Commander Policy Controls */}
        <div className="p-3 bg-surface border border-rule space-y-3">
          <div className="flex justify-between items-center">
            <div className="text-xs font-medium text-ink-2">Commander policy</div>
            <div className="flex space-x-1">
              {(["cautious", "balanced", "aggressive"] as const).map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => handleApplyPreset(p)}
                  className={`px-2 py-0.5 text-[11px] font-mono border ${
                    policy.preset === p ? "border-attention bg-surface-raised text-attention" : "border-rule text-ink-3"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2 text-xs">
            <div>
              <div className="flex justify-between text-ink-3 font-mono text-[11px]">
                <span>Acceptable agent-loss risk</span>
                <span>{Math.round(policy.agentLossLimit * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="0.25"
                step="0.01"
                value={policy.agentLossLimit}
                onChange={(e) =>
                  setPolicy((prev) => ({ ...prev, agentLossLimit: parseFloat(e.target.value) }))
                }
                className="w-full accent-[#D8A24A]"
              />
            </div>

            <div>
              <div className="flex justify-between text-ink-3 font-mono text-[11px]">
                <span>P1 critical delivery floor</span>
                <span>{Math.round(policy.p1Floor * 100)}%</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="1.0"
                step="0.05"
                value={policy.p1Floor}
                onChange={(e) =>
                  setPolicy((prev) => ({ ...prev, p1Floor: parseFloat(e.target.value) }))
                }
                className="w-full accent-[#D8A24A]"
              />
            </div>

            <div className="grid grid-cols-3 gap-2 pt-1 font-mono text-[11px]">
              <div className="p-1.5 border border-rule bg-surface-raised text-center">
                <span className="text-ink-3 block">P1 Weight</span>
                <span className="text-ink font-medium">{policy.p1Weight}</span>
              </div>
              <div className="p-1.5 border border-rule bg-surface-raised text-center">
                <span className="text-ink-3 block">P2 Weight</span>
                <span className="text-ink font-medium">{policy.p2Weight}</span>
              </div>
              <div className="p-1.5 border border-rule bg-surface-raised text-center">
                <span className="text-ink-3 block">P3 Weight</span>
                <span className="text-ink font-medium">{policy.p3Weight}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Swarm Roster & Capabilities Table */}
        <div className="p-3 bg-surface border border-rule space-y-2">
          <div className="text-xs font-medium text-ink-2">Swarm roster and asset capabilities</div>
          <table className="w-full text-xs text-left border-collapse font-mono">
            <thead>
              <tr className="border-b border-rule bg-surface-raised text-ink-3 text-[11px]">
                <th className="py-1 px-2 font-normal">Asset</th>
                <th className="py-1 px-2 font-normal">Class</th>
                <th className="py-1 px-2 font-normal">Sensor / Payload</th>
                <th className="py-1 px-2 font-normal text-right">Comms</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule text-[11px]">
              {agentSpecs.map((spec) => (
                <tr key={spec.id} className="hover:bg-surface-raised">
                  <td className="py-1.5 px-2 font-medium text-ink">{spec.id}</td>
                  <td className="py-1.5 px-2 text-ink-2">{spec.type}</td>
                  <td className="py-1.5 px-2 text-ink-3">{spec.sensor}</td>
                  <td className="py-1.5 px-2 text-right text-ink-2">{spec.comms}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

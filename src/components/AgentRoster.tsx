import React from "react";
import { AgentState } from "../types";

interface AgentRosterProps {
  agents: Record<string, AgentState>;
  selectedAgentId?: string | null;
  onSelectAgent: (id: string | null) => void;
}

export const AgentRoster: React.FC<AgentRosterProps> = ({
  agents,
  selectedAgentId,
  onSelectAgent,
}) => {
  const agentList = Object.values(agents);

  return (
    <div className="border-b border-rule bg-surface select-none">
      <div className="px-3 py-1.5 text-xs text-ink-2 font-sans font-medium border-b border-rule flex justify-between items-center">
        <span>Agent roster</span>
        <span className="font-mono text-ink-3 text-[11px]">{agentList.length} active</span>
      </div>

      <table className="w-full text-xs text-left border-collapse">
        <thead>
          <tr className="border-b border-rule bg-surface-raised text-ink-3 font-sans text-[11px]">
            <th className="py-1 px-3 font-normal">ID</th>
            <th className="py-1 px-2 font-normal">Link</th>
            <th className="py-1 px-3 font-normal">Battery</th>
            <th className="py-1 px-3 font-normal">Task</th>
            <th className="py-1 px-3 font-normal text-right">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-rule font-mono">
          {agentList.map((ag) => {
            const isSel = ag.id === selectedAgentId;
            const batPct = Math.round(ag.battery * 100);
            const resPct = Math.round(ag.reserve_required * 100);
            const isLowBat = ag.battery <= ag.reserve_required;

            return (
              <tr
                key={ag.id}
                onClick={() => onSelectAgent(isSel ? null : ag.id)}
                className={`h-9 cursor-pointer transition-colors ${
                  isSel ? "bg-surface-raised text-attention" : "hover:bg-surface-raised text-ink"
                }`}
              >
                <td className="py-1 px-3 font-medium flex items-center space-x-2">
                  <span className="w-2 h-2 bg-rule-strong inline-block" />
                  <span>{ag.id}</span>
                </td>

                <td className="py-1 px-2">
                  <span
                    className={`inline-block w-2 h-2 ${
                      ag.connected ? "bg-fact" : "bg-safety"
                    }`}
                    title={ag.connected ? "Connected" : "Disconnected"}
                  />
                </td>

                <td className="py-1 px-3">
                  <div className="w-24 bg-rule h-2 relative">
                    {/* Battery Fill */}
                    <div
                      className={`h-full ${isLowBat ? "bg-safety" : "bg-fact"}`}
                      style={{ width: `${Math.min(100, Math.max(0, batPct))}%` }}
                    />
                    {/* Reserve Tick Mark */}
                    <div
                      className="absolute top-0 bottom-0 w-0.5 bg-attention"
                      style={{ left: `${resPct}%` }}
                      title={`Reserve threshold: ${resPct}%`}
                    />
                  </div>
                  <div className="text-[10px] text-ink-3 mt-0.5">
                    {batPct}% · res {resPct}%
                  </div>
                </td>

                <td className="py-1 px-3 text-ink-2 truncate max-w-[120px]">
                  {ag.queue.length > 0 ? ag.queue[0] : "idle"}
                </td>

                <td className="py-1 px-3 text-right">
                  <span
                    className={`text-[11px] font-mono ${
                      ag.status === "executing"
                        ? "text-fact"
                        : ag.status === "holding"
                        ? "text-attention"
                        : ag.status === "rtb" || ag.status === "lost"
                        ? "text-safety"
                        : "text-ink-3"
                    }`}
                  >
                    {ag.status}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

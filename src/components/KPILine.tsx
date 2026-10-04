import React from "react";
import { KPIData } from "../types";

interface KPILineProps {
  kpis: KPIData;
}

export const KPILine: React.FC<KPILineProps> = ({ kpis }) => {
  return (
    <div className="h-8 border-b border-rule bg-surface flex items-center text-xs px-4 divide-x divide-rule overflow-hidden select-none">
      <div className="flex items-center space-x-2 pr-4">
        <span className="text-ink-3">Expected aid</span>
        <span className="font-mono text-ink text-lg font-medium tabular-nums">
          {kpis.expected_aid.toFixed(2)}
        </span>
      </div>

      <div className="flex items-center space-x-2 px-4">
        <span className="text-ink-3">Survivors aided</span>
        <span className="font-mono text-ink text-lg font-medium tabular-nums">
          {kpis.survivors_aided}
        </span>
      </div>

      <div className="flex items-center space-x-2 px-4">
        <span className="text-ink-3">P1 at risk</span>
        <span
          className={`font-mono text-lg font-medium tabular-nums ${
            kpis.p1_at_risk > 0 ? "text-safety" : "text-ink"
          }`}
        >
          {kpis.p1_at_risk}
        </span>
      </div>

      <div className="flex items-center space-x-2 px-4">
        <span className="text-ink-3">Time to infeasibility</span>
        <span className="font-mono text-ink text-lg font-medium tabular-nums">
          {kpis.tti_s !== null && kpis.tti_s !== undefined ? `${kpis.tti_s}s` : "none"}
        </span>
      </div>

      <div className="flex items-center space-x-2 px-4">
        <span className="text-ink-3">Escalations/hr</span>
        <span className="font-mono text-ink text-lg font-medium tabular-nums">
          {kpis.escalations_per_hour.toFixed(1)}
        </span>
      </div>

      <div className="flex items-center space-x-2 px-4">
        <span className="text-ink-3">Agents lost</span>
        <span
          className={`font-mono text-lg font-medium tabular-nums ${
            kpis.agents_lost > 0 ? "text-safety font-bold" : "text-ink"
          }`}
        >
          {kpis.agents_lost}
        </span>
      </div>
    </div>
  );
};

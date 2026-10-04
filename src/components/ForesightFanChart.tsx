import React from "react";
import { Forecast } from "../types";

interface ForesightFanChartProps {
  forecast?: Forecast | null;
}

export const ForesightFanChart: React.FC<ForesightFanChartProps> = ({ forecast }) => {
  if (!forecast || !forecast.candidates || forecast.candidates.length === 0) {
    return (
      <div className="h-44 border-b border-rule bg-surface p-3 flex flex-col justify-center items-center text-xs text-ink-3 font-mono">
        <span>Awaiting first forecast</span>
      </div>
    );
  }

  const candidates = forecast.candidates;
  const isValueTradeoff = forecast.classification === "VALUE";

  return (
    <div className="border-b border-rule bg-surface p-3 flex flex-col justify-between select-none">
      <div className="flex justify-between items-center mb-2">
        <div className="flex items-center space-x-2">
          <span className="text-xs text-ink-2 font-sans font-medium">Foresight</span>
          <span className="text-xs text-ink-3 font-mono">
            rollouts (N={forecast.n_rollouts})
          </span>
          <span
            className={`px-1 text-[10px] font-mono border ${
              isValueTradeoff
                ? "border-attention text-attention"
                : "border-fact text-fact"
            }`}
          >
            {forecast.classification}
          </span>
        </div>
        <span className="text-[11px] text-ink-3 font-mono">
          epoch {forecast.epoch} · seed {forecast.crn_seed}
        </span>
      </div>

      {/* Candidates Comparison Table & Bars */}
      <div className="space-y-3 my-1">
        {candidates.map((cand) => {
          const barWidth = Math.min(100, Math.max(10, (cand.esa_mean / 4.0) * 100));
          const lossPct = Math.round(cand.p_agent_loss * 100);

          return (
            <div key={cand.plan_id} className="text-xs font-mono space-y-1">
              <div className="flex justify-between text-ink-2">
                <span className="font-medium text-ink">{cand.plan_id}</span>
                <span>
                  ESA {cand.esa_mean.toFixed(2)}{" "}
                  <span className="text-ink-3 text-[11px]">
                    [{cand.esa_ci95[0].toFixed(2)}, {cand.esa_ci95[1].toFixed(2)}]
                  </span>
                  {" · "}
                  <span className={lossPct > 10 ? "text-safety" : "text-ink-3"}>
                    loss {lossPct}%
                  </span>
                </span>
              </div>

              {/* Square-ended bar with CI whisker */}
              <div className="w-full bg-rule h-4 relative">
                <div
                  className="h-full bg-policy"
                  style={{ width: `${barWidth}%` }}
                />
                {/* 95% Confidence Interval Whisker */}
                <div
                  className="absolute top-1 bottom-1 border-y border-attention"
                  style={{
                    left: `${Math.min(100, (cand.esa_ci95[0] / 4.0) * 100)}%`,
                    width: `${Math.max(4, ((cand.esa_ci95[1] - cand.esa_ci95[0]) / 4.0) * 100)}%`,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Reason / Decision rule explanation */}
      <div className="text-[11px] text-ink-3 font-mono mt-2 pt-2 border-t border-rule leading-relaxed break-words">
        {forecast.reason}
      </div>
    </div>
  );
};

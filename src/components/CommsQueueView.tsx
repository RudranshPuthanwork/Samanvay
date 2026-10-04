import React from "react";
import { CommsPayload } from "../types";

interface CommsQueueViewProps {
  comms?: CommsPayload | null;
}

export const CommsQueueView: React.FC<CommsQueueViewProps> = ({ comms }) => {
  const queue = comms?.queue || [];
  const budget = comms?.budget_remaining ?? 4;

  return (
    <div className="h-16 border-b border-rule bg-surface px-3 py-1.5 flex flex-col justify-between select-none font-mono text-xs">
      <div className="flex justify-between items-center text-[11px] text-ink-3">
        <span className="font-sans font-medium text-ink-2 text-xs">Comms queue (VoI priority)</span>
        <span>
          Budget: <span className="text-ink font-medium">{budget}/4</span> pkts
        </span>
      </div>

      <div className="flex items-center space-x-2 overflow-x-auto py-1">
        {queue.length === 0 ? (
          <span className="text-ink-3 text-[11px]">Queue empty</span>
        ) : (
          queue.map((item) => (
            <div
              key={item.id}
              className="px-2 py-0.5 bg-surface-raised border border-rule flex items-center space-x-1 text-[11px] shrink-0"
            >
              <span className="text-ink font-medium">{item.recipient}</span>
              <span className="text-ink-3">·</span>
              <span className="text-attention">{item.type}</span>
              <span className="text-ink-3 text-[10px]">({item.voi_score.toFixed(2)})</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

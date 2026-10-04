import React from "react";
import { DecisionRecord } from "../types";

interface DecisionLogProps {
  records: DecisionRecord[];
  selectedRecordId?: number | null;
  onSelectRecord?: (record: DecisionRecord) => void;
}

export const DecisionLog: React.FC<DecisionLogProps> = ({
  records,
  selectedRecordId,
  onSelectRecord,
}) => {
  return (
    <div className="flex-1 border-b border-rule bg-surface flex flex-col min-h-0 select-none">
      <div className="px-3 py-1.5 text-xs text-ink-2 font-sans font-medium border-b border-rule flex justify-between items-center">
        <span>Decision log</span>
        <span className="font-mono text-ink-3 text-[11px]">{records.length} records (SHA-256)</span>
      </div>

      <div className="flex-1 overflow-y-auto divide-y divide-rule font-mono text-xs">
        {records.length === 0 ? (
          <div className="p-4 text-ink-3 text-center">No decisions logged</div>
        ) : (
          records
            .slice()
            .reverse()
            .map((rec) => {
              const mins = Math.floor(rec.t / 60);
              const secs = Math.floor(rec.t % 60);
              const timeStr = `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;

              const textColor =
                rec.classification === "FACT"
                  ? "text-fact"
                  : rec.classification === "VALUE"
                  ? "text-attention"
                  : rec.classification === "POLICY"
                  ? "text-policy"
                  : "text-safety";

              const isSelected = selectedRecordId === rec.id;

              return (
                <div
                  key={rec.id}
                  onClick={() => onSelectRecord?.(rec)}
                  className={`p-2.5 cursor-pointer transition-colors space-y-1 ${
                    isSelected ? "bg-surface-raised ring-1 ring-inset ring-rule-strong" : "hover:bg-surface-raised"
                  }`}
                >
                  <div className="flex items-center justify-between text-[11px]">
                    <div className="flex items-center space-x-2">
                      <span className="text-ink-3 tabular-nums">{timeStr}</span>
                      <span className="font-medium text-ink">{rec.kind}</span>
                      <span className={`text-[10px] font-mono ${textColor}`}>
                        {rec.classification.toLowerCase()}
                      </span>
                    </div>
                    <span className="text-ink-3 text-[10px] font-mono" title={`Full hash: ${rec.hash}`}>
                      #{rec.id} · {rec.hash.slice(0, 6)}
                    </span>
                  </div>

                  <p className="text-ink-2 font-sans text-xs leading-normal">
                    {rec.explanation}
                  </p>
                </div>
              );
            })
        )}
      </div>
    </div>
  );
};

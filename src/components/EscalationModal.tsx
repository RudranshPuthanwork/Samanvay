import React, { useEffect, useState } from "react";
import { EscalationPayload } from "../types";

interface EscalationModalProps {
  escalation: EscalationPayload;
  onSelectOption: (optionId: string) => void;
  onHoverOption?: (optionId: string | null) => void;
}

export const EscalationModal: React.FC<EscalationModalProps> = ({
  escalation,
  onSelectOption,
  onHoverOption,
}) => {
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [timeLeft, setTimeLeft] = useState(Math.round(escalation.deadline_s));

  useEffect(() => {
    const opt = escalation.options[selectedIdx];
    if (opt) {
      onHoverOption?.(opt.id);
    }
    return () => onHoverOption?.(null);
  }, [selectedIdx, escalation.options, onHoverOption]);

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeLeft((t) => {
        if (t <= 1) {
          clearInterval(timer);
          onSelectOption(escalation.default_option_id);
          return 0;
        }
        return t - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [escalation, onSelectOption]);

  // Keyboard navigation: ArrowUp, ArrowDown, Enter
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIdx((prev) => (prev + 1) % escalation.options.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIdx((prev) => (prev - 1 + escalation.options.length) % escalation.options.length);
      } else if (e.key === "Enter") {
        e.preventDefault();
        const opt = escalation.options[selectedIdx];
        if (opt) {
          onSelectOption(opt.id);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [escalation.options, selectedIdx, onSelectOption]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ground/80 p-4 select-none">
      <div className="w-[620px] bg-surface border border-rule-strong p-5 space-y-4">
        {/* Header */}
        <div className="flex justify-between items-start border-b border-rule pb-3">
          <div>
            <div className="text-xs font-mono text-ink-3">Escalation required · Value conflict</div>
            <h2 className="text-base font-medium text-ink mt-0.5">Plan trade-off deliberation</h2>
            <p className="text-ink-2 text-xs mt-1 font-sans">{escalation.trigger_reason}</p>
          </div>
          <div className="text-right">
            <span className="text-[11px] text-ink-3 font-mono">Timeout</span>
            <div className="font-mono text-base font-medium text-ink tabular-nums">
              {timeLeft}s
            </div>
          </div>
        </div>

        {/* Options Table (not cards!) */}
        <div className="border border-rule divide-y divide-rule font-mono text-xs">
          {escalation.options.map((opt, idx) => {
            const isSel = idx === selectedIdx;
            return (
              <div
                key={opt.id}
                onClick={() => {
                  setSelectedIdx(idx);
                }}
                className={`p-3 cursor-pointer transition-colors flex items-start justify-between space-x-4 ${
                  isSel ? "bg-surface-raised" : "hover:bg-surface-raised"
                }`}
              >
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="text-ink-3 text-xs">{isSel ? ">" : " "}</span>
                    <span className="font-medium text-ink">{opt.title}</span>
                    {opt.is_default && (
                      <span className="text-[11px] text-ink-3 font-mono">
                        (default)
                      </span>
                    )}
                  </div>
                  <p className="font-sans text-xs text-ink-2 leading-relaxed pl-4">
                    {opt.tradeoff_summary}
                  </p>
                </div>

                <div className="text-right shrink-0">
                  <span className="text-xs text-ink font-medium">
                    ESA {opt.esa_ci95[0].toFixed(2)}–{opt.esa_ci95[1].toFixed(2)}
                  </span>
                  <div className="text-[11px] text-ink-3">
                    loss risk {(opt.p_agent_loss * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Actions & Keyboard hints */}
        <div className="flex justify-between items-center pt-2 border-t border-rule">
          <span className="text-xs text-ink-3 font-mono">
            Navigate with ↑ / ↓, press Enter to confirm
          </span>
          <button
            type="button"
            onClick={() => {
              const opt = escalation.options[selectedIdx];
              if (opt) onSelectOption(opt.id);
            }}
            className="px-3 py-1 bg-surface-raised border border-rule-strong hover:border-attention text-ink font-mono text-xs"
          >
            Confirm {escalation.options[selectedIdx]?.id || "option"}
          </button>
        </div>
      </div>
    </div>
  );
};

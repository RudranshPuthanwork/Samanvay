import React, { useState } from "react";

interface CommandLineProps {
  onSubmit: (text: string) => void;
  lastMission?: string | null;
}

export const CommandLine: React.FC<CommandLineProps> = ({ onSubmit, lastMission }) => {
  const [inputVal, setInputVal] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim()) return;
    onSubmit(inputVal.trim());
    setInputVal("");
  };

  return (
    <div className="relative border-t border-rule bg-surface select-none">
      {lastMission && (
        <div className="px-4 py-1 bg-surface-raised border-b border-rule text-xs font-mono text-ink-3 flex items-center justify-between">
          <span className="truncate">Active Mission: {lastMission}</span>
          <span className="text-fact text-[10px] font-medium">Confirmed</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="h-9 px-4 flex items-center space-x-2 font-mono text-xs relative">
        <span className="text-attention font-bold text-sm">{">"}</span>
        <div className="flex-1 relative flex items-center">
          <input
            type="text"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            aria-label="Mission objective"
            className="w-full bg-transparent border-none text-ink focus:outline-none font-mono text-xs z-10"
          />
          {!inputVal && (
            <span className="absolute left-0 text-ink-3 font-mono text-xs pointer-events-none">
              Type mission objective (e.g. Sweep all sectors, focus on B and C, deliver medkits, avoid plume)
            </span>
          )}
        </div>
        <button
          type="submit"
          className="px-2.5 py-0.5 border border-rule hover:border-attention hover:text-attention text-ink-2 bg-surface-raised font-mono text-xs z-10"
        >
          Submit
        </button>
      </form>
    </div>
  );
};

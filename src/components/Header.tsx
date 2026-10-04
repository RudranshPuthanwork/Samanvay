import React from "react";

interface HeaderProps {
  scenarioId: string;
  seed: number;
  simTime: number;
  isRunning: boolean;
  speed: number;
  theme: "dark" | "light";
  activeStage: "brief" | "operate" | "review";
  missionConfirmed: boolean;
  judgeMode: boolean;
  onSelectStage: (stage: "brief" | "operate" | "review") => void;
  onTogglePlay: () => void;
  onSetSpeed: (s: number) => void;
  onToggleTheme: () => void;
  onToggleJudgeMode: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  scenarioId,
  seed,
  simTime,
  isRunning,
  speed,
  theme,
  activeStage,
  missionConfirmed,
  judgeMode,
  onSelectStage,
  onTogglePlay,
  onSetSpeed,
  onToggleTheme,
  onToggleJudgeMode,
}) => {
  const mins = Math.floor(simTime / 60);
  const secs = Math.floor(simTime % 60);
  const formattedTime = `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;

  return (
    <header className="h-10 border-b border-rule bg-surface px-4 flex items-center justify-between select-none font-sans">
      <div className="flex items-center space-x-3">
        <span className="font-medium text-ink text-base tracking-tight">SAMANVAY</span>
        <span className="text-ink-3 text-xs">समन्वय</span>
        <span className="text-ink-3 text-xs border-l border-rule pl-3 font-mono">
          {scenarioId} · seed {seed}
        </span>
      </div>

      {/* One-Line Stage Switch: Brief, Operate, Review (Spec §19) */}
      <div className="flex border border-rule">
        {(["brief", "operate", "review"] as const).map((stage) => {
          const isSel = activeStage === stage;
          const label = stage === "brief" ? "Brief" : stage === "operate" ? "Operate" : "Review";
          return (
            <button
              key={stage}
              type="button"
              onClick={() => onSelectStage(stage)}
              className={`px-3 py-1 text-xs transition-colors ${
                isSel ? "bg-surface-raised text-ink font-medium" : "text-ink-3 hover:text-ink hover:bg-surface-raised"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>

      <div className="flex items-center space-x-3 text-xs">
        {/* Clock: awaiting mission before confirmation */}
        <span className="font-mono text-ink text-xs tabular-nums mr-1">
          {!missionConfirmed ? (
            <span className="text-ink-3">awaiting mission</span>
          ) : (
            formattedTime
          )}
        </span>

        {activeStage === "operate" && (
          <>
            <button
              type="button"
              onClick={onTogglePlay}
              className="px-2 py-1 border border-rule hover:border-rule-strong text-ink bg-surface-raised font-mono text-xs"
            >
              {isRunning ? "Pause [Space]" : "Play [Space]"}
            </button>

            <div className="flex border border-rule font-mono">
              {[1, 2, 5].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => onSetSpeed(s)}
                  className={`px-2 py-1 text-xs ${
                    speed === s ? "bg-surface-raised text-ink font-medium" : "text-ink-3 hover:text-ink hover:bg-surface-raised"
                  }`}
                >
                  {s}×
                </button>
              ))}
            </div>
          </>
        )}

        <button
          type="button"
          onClick={onToggleJudgeMode}
          className={`px-2 py-1 border text-xs font-mono ${
            judgeMode ? "border-rule-strong text-ink bg-surface-raised font-medium" : "border-rule text-ink-3 hover:text-ink"
          }`}
        >
          Judge mode
        </button>

        <button
          type="button"
          onClick={onToggleTheme}
          className="px-2 py-1 border border-rule text-ink-3 hover:text-ink hover:border-rule-strong"
        >
          {theme === "dark" ? "Light theme" : "Dark theme"}
        </button>
      </div>
    </header>
  );
};

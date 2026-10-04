import React from "react";

interface EventInjectionRowProps {
  /** Returns false if the event could not be sent (server not connected). */
  onInject: (eventType: string, params?: Record<string, unknown>) => boolean | void;
  connected?: boolean;
}

export const EventInjectionRow: React.FC<EventInjectionRowProps> = ({ onInject, connected = true }) => {
  const [status, setStatus] = React.useState<{ text: string; ok: boolean } | null>(null);
  const timerRef = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  React.useEffect(() => () => clearTimeout(timerRef.current), []);

  const events = [
    { label: "Aftershock", type: "AFTERSHOCK", params: { cells: [[24, 30], [25, 30]] } },
    { label: "Comms loss", type: "COMMS_LOSS", params: { agent_id: "scout-2" } },
    { label: "Weather change", type: "WEATHER_CHANGE", params: { wind_deg: 270, wind_mps: 6.5 } },
    { label: "Battery fault", type: "BATTERY_FAULT", params: { agent_id: "cargo-1" } },
    { label: "Agent failure", type: "AGENT_FAILURE", params: { agent_id: "rover-1" } },
    { label: "Detection", type: "DETECTION", params: { cell: [38, 14], posterior: 0.88 } },
  ];

  const handleClick = (label: string, type: string, params?: Record<string, unknown>) => {
    const sent = onInject(type, params) !== false;
    setStatus(sent ? { text: `injected: ${label}`, ok: true } : { text: `not sent (server offline): ${label}`, ok: false });
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setStatus(null), 2000);
  };

  return (
    <div className="h-9 border-t border-rule bg-surface px-4 flex items-center space-x-3 text-xs select-none">
      <span className="text-ink-2 font-sans font-medium text-xs">
        Inject event:
      </span>
      <div className="flex items-center space-x-2">
        {events.map((ev) => (
          <button
            key={ev.type}
            id={`inject-${ev.type.toLowerCase()}`}
            type="button"
            disabled={!connected}
            onClick={() => handleClick(ev.label, ev.type, ev.params)}
            className="px-2 py-0.5 border border-rule hover:border-attention hover:text-attention active:scale-95 text-ink-2 bg-surface-raised font-mono text-xs transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:border-rule disabled:hover:text-ink-2"
          >
            {ev.label}
          </button>
        ))}
      </div>
      {!connected && (
        <span className="text-attention font-mono text-xs ml-2">server offline, reconnecting...</span>
      )}
      {connected && status && (
        <span className={`${status.ok ? "text-attention" : "text-ink-2"} font-mono text-xs ml-2`}>
          {status.text}
        </span>
      )}
    </div>
  );
};

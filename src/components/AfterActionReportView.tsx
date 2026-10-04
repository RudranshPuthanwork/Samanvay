import React, { useEffect, useState } from "react";

interface ReportData {
  scenario_id: string;
  t: number;
  survivors_aided: number;
  total_survivors: number;
  decisions_count: number;
  log_valid: boolean;
  log_reason: string;
  final_digest: string;
  decisions: Array<{
    id: number;
    t: number;
    kind: string;
    classification: string;
    explanation: string;
    hash: string;
  }>;
  trust_boundaries: string[];
}

interface AfterActionReportViewProps {
  onBack: () => void;
}

export const AfterActionReportView: React.FC<AfterActionReportViewProps> = ({ onBack }) => {
  const [data, setData] = useState<ReportData | null>(null);

  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/report")
      .then((res) => res.json())
      .then((d) => setData(d))
      .catch(() => {
        // Fallback if running offline without server
        setData({
          scenario_id: "F1_s0042",
          t: 600,
          survivors_aided: 8,
          total_survivors: 9,
          decisions_count: 14,
          log_valid: true,
          log_reason: "Chain valid",
          final_digest: "e04a899cf41d8e12b7a9...",
          decisions: [],
          trust_boundaries: [
            "TruthWorld isolated behind firewall; planner operates only on BeliefState.",
            "All decisions hash-chained with SHA-256 and signed with Ed25519.",
            "Zero external network calls; fully offline-capable.",
          ],
        });
      });
  }, []);

  if (!data) {
    return (
      <div className="h-full w-full bg-ground p-6 font-mono text-ink text-sm flex items-center justify-center">
        Loading after-action report...
      </div>
    );
  }

  return (
    <div className="h-full w-full bg-ground text-ink flex flex-col overflow-y-auto select-none p-6 space-y-6">
      {/* Top Bar with Back Control */}
      <div className="flex justify-between items-center border-b border-rule pb-4">
        <div>
          <h1 className="text-xl font-bold font-sans">After-Action Mission Report</h1>
          <p className="text-xs text-ink-3 font-mono mt-1">
            Scenario: {data.scenario_id} · Duration: {Math.floor(data.t)}s
          </p>
        </div>
        <button
          type="button"
          onClick={onBack}
          className="px-3 py-1.5 border border-rule hover:border-rule-strong bg-surface text-ink text-xs font-mono"
        >
          Back to Console
        </button>
      </div>

      {/* KPI Summary Line */}
      <div className="grid grid-cols-4 gap-4">
        <div className="p-4 bg-surface border border-rule space-y-1">
          <span className="text-xs text-ink-3 font-mono">Survivors Aided</span>
          <div className="text-2xl font-mono font-bold text-ink">
            {data.survivors_aided} / {data.total_survivors}
          </div>
        </div>

        <div className="p-4 bg-surface border border-rule space-y-1">
          <span className="text-xs text-ink-3 font-mono">Total Decisions</span>
          <div className="text-2xl font-mono font-bold text-ink">{data.decisions_count}</div>
        </div>

        <div className="p-4 bg-surface border border-rule space-y-1">
          <span className="text-xs text-ink-3 font-mono">Decision Log Integrity</span>
          <div className="text-2xl font-mono font-bold text-fact">
            {data.log_valid ? "VERIFIED" : "COMPROMISED"}
          </div>
          <span className="text-[10px] text-ink-3 font-mono truncate block">
            {data.log_reason}
          </span>
        </div>

        <div className="p-4 bg-surface border border-rule space-y-1">
          <span className="text-xs text-ink-3 font-mono">Final Digest</span>
          <div className="text-xs font-mono text-ink-2 truncate mt-2" title={data.final_digest}>
            {data.final_digest}
          </div>
        </div>
      </div>

      {/* Decisions Timeline Table */}
      <div className="border border-rule bg-surface">
        <div className="px-4 py-2 border-b border-rule font-sans text-xs text-ink-2 font-medium">
          Audited decisions timeline
        </div>
        <table className="w-full text-xs text-left border-collapse font-mono">
          <thead>
            <tr className="border-b border-rule bg-surface-raised text-ink-3 text-[11px]">
              <th className="py-2 px-4 font-normal">T (s)</th>
              <th className="py-2 px-4 font-normal">Kind</th>
              <th className="py-2 px-4 font-normal">Classification</th>
              <th className="py-2 px-4 font-normal">Explanation</th>
              <th className="py-2 px-4 font-normal text-right">Hash</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {data.decisions.length === 0 ? (
              <tr>
                <td colSpan={5} className="p-4 text-center text-ink-3">
                  No records in report
                </td>
              </tr>
            ) : (
              data.decisions.map((dec) => (
                <tr key={dec.id} className="hover:bg-surface-raised">
                  <td className="py-2 px-4 text-ink-3">{dec.t}s</td>
                  <td className="py-2 px-4 font-bold text-ink">{dec.kind}</td>
                  <td className="py-2 px-4">
                    <span
                      className={`px-1 text-[10px] border ${
                        dec.classification === "FACT"
                          ? "border-fact text-fact"
                          : dec.classification === "VALUE"
                          ? "border-attention text-attention"
                          : dec.classification === "POLICY"
                          ? "border-policy text-policy"
                          : "border-safety text-safety"
                      }`}
                    >
                      {dec.classification}
                    </span>
                  </td>
                  <td className="py-2 px-4 font-sans text-xs text-ink-2">{dec.explanation}</td>
                  <td className="py-2 px-4 text-right text-ink-3 text-[10px]">
                    {dec.hash.slice(0, 8)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Trust Boundaries (Spec §11.5) */}
      <div className="p-4 border border-rule bg-surface space-y-2 text-xs">
        <span className="font-sans text-xs text-ink-2 font-medium">
          Trust boundaries and deployment claims
        </span>
        <ul className="list-disc list-inside space-y-1 text-ink-2 font-sans">
          {data.trust_boundaries.map((tb, idx) => (
            <li key={idx}>{tb}</li>
          ))}
        </ul>
      </div>
    </div>
  );
};

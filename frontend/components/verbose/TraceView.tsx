"use client";

import type { AgentTrace } from "@/lib/schemas";

const MODE_STYLE: Record<string, string> = {
  live: "bg-green-100 text-green-800",
  error: "bg-amber-100 text-amber-800",
  disabled: "bg-slate-100 text-slate-500",
};

const MODE_LABEL: Record<string, string> = {
  live: "live LLM",
  error: "fallback",
  disabled: "disabled",
};

export function TraceView({ trace }: { trace: AgentTrace[] | null | undefined }) {
  const rows = trace ?? [];
  const live = rows.filter((r) => r.mode === "live").length;
  const totalMs = rows.reduce((a, r) => a + (r.latency_ms || 0), 0);
  return (
    <div className="grid gap-4">
      <div className="rounded-lg border border-slate-200 p-4 text-sm">
        <strong>Agentic run — verbose.</strong>{" "}
        {rows.length === 0 ? (
          <span className="text-slate-500">No LLM calls recorded (deterministic run).</span>
        ) : (
          <span className="text-slate-600">
            {rows.length} LLM call{rows.length === 1 ? "" : "s"} · {live} live ·{" "}
            {(totalMs / 1000).toFixed(1)}s total LLM time.
          </span>
        )}
      </div>
      {rows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                <th className="px-3 py-2">Agent task</th>
                <th className="px-3 py-2">Provider / model</th>
                <th className="px-3 py-2">Latency</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Detail</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-b border-slate-100 last:border-0">
                  <td className="px-3 py-2 font-mono text-xs">{r.node}</td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {r.provider} / {r.model}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {(r.latency_ms / 1000).toFixed(1)}s
                  </td>
                  <td className="px-3 py-2">
                    <span className={`rounded px-2 py-0.5 text-xs font-medium ${MODE_STYLE[r.mode] ?? MODE_STYLE.disabled}`}>
                      {MODE_LABEL[r.mode] ?? r.mode}
                    </span>
                  </td>
                  <td className="max-w-xs truncate px-3 py-2 text-xs text-slate-500" title={r.detail ?? ""}>
                    {r.mode === "live" ? "—" : r.detail ?? ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

"use client";

import { Badge } from "@/components/ui/badge";
import { scoreColor } from "@/lib/format";
import type { ATSResult } from "@/lib/schemas";

const BAR_KEYS = ["keyword", "skill", "semantic", "experience", "education", "project_relevance"] as const;
const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function gaugeColor(score: number): string {
  if (score >= 75) return "#10b981";
  if (score >= 50) return "#f59e0b";
  return "#ef4444";
}

/** Render LLM rationale as a clean bullet list. Strips markdown the model
 *  sometimes emits (**bold**, "- " bullets) so it always reads well. */
function Rationale({ text }: { text: string }) {
  const items = (text || "")
    .split(/\n+/)
    .flatMap((line) => line.split(/\s+-\s+(?=\*\*|\w)/))
    .map((s) => s.replace(/\*\*/g, "").replace(/^[-–•\s]+/, "").trim())
    .filter(Boolean)
    .slice(0, 6);
  if (items.length <= 1) {
    return <p className="mt-3 break-words text-sm leading-relaxed text-slate-600">{items[0] ?? text}</p>;
  }
  return (
    <ul className="mt-3 list-disc space-y-1 break-words pl-5 text-sm leading-relaxed text-slate-600">
      {items.map((s, i) => (
        <li key={i}>{s}</li>
      ))}
    </ul>
  );
}

export function AtsScore({ result }: { result: ATSResult }) {
  const score = Math.max(0, Math.min(100, Math.round(result.score)));
  const dash = (CIRCUMFERENCE * score) / 100;

  return (
    <div className="grid gap-6 rounded-xl border border-slate-200 bg-white p-6 lg:grid-cols-2">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
        <div className="relative mx-auto h-36 w-36 shrink-0 sm:mx-0">
          <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
            <circle cx="60" cy="60" r={RADIUS} fill="none" stroke="#e2e8f0" strokeWidth="10" />
            <circle
              cx="60"
              cy="60"
              r={RADIUS}
              fill="none"
              stroke={gaugeColor(score)}
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={`${dash} ${CIRCUMFERENCE}`}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={`text-4xl font-extrabold leading-none ${scoreColor(score)}`}>{score}</span>
            <span className="mt-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">of 100</span>
          </div>
        </div>
        <div className="min-w-0 flex-1">
          <Badge tone={score >= 75 ? "green" : score >= 50 ? "amber" : "red"}>{result.verdict}</Badge>
          <Rationale text={result.rationale} />
        </div>
      </div>

      <div className="min-w-0 lg:border-l lg:border-slate-200 lg:pl-6">
        <h3 className="text-sm font-semibold">6-way breakdown</h3>
        <ul className="mt-3 space-y-2">
          {BAR_KEYS.map((k) => {
            const v = result.breakdown[k];
            return (
              <li key={k} className="grid grid-cols-[7.5rem_minmax(0,1fr)_2.25rem] items-center gap-2 text-sm">
                <span className="capitalize text-slate-600">{k.replaceAll("_", " ")}</span>
                <div className="h-2 overflow-hidden rounded-full bg-slate-200">
                  <div className="h-full rounded-full bg-blue-600" style={{ width: `${v ?? 0}%` }} />
                </div>
                <span className="text-right tabular-nums text-slate-700">{v == null ? "n/a" : Math.round(v)}</span>
              </li>
            );
          })}
        </ul>
        <div className="mt-4 grid gap-2 text-sm leading-relaxed">
          <p className="break-words">
            <strong>Strengths:</strong> {result.strengths.join(", ") || "—"}
          </p>
          <p className="break-words">
            <strong>Gaps:</strong> {result.gaps.join(", ") || "—"}
          </p>
        </div>
      </div>
    </div>
  );
}

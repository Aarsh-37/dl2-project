import { CheckCircle2, Loader2, Circle } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import type { NodeStatus } from "@/lib/useStream";

const LABELS: Record<string, string> = {
  resume_analyzer: "Resume analyzed",
  jd_analyzer: "JD analyzed",
  ats_engine: "ATS calculated",
  skill_gap: "Skills compared",
  roadmap: "Building roadmap",
  interview: "Preparing interview Qs",
  optimizer: "Optimizing resume",
  validator: "Validating resume",
  coach: "Career advice",
};

export function ProgressHeader({
  events,
  percent,
  done,
}: {
  events: Record<string, NodeStatus>;
  percent: number;
  done: boolean;
}) {
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">AI Career Analysis {done ? "— done" : `— ${percent}%`}</h2>
      </div>
      <Progress value={percent} />
      <ul className="mt-3 grid gap-1 text-sm sm:grid-cols-2">
        {Object.keys(LABELS).map((node) => {
          const st = events[node];
          return (
            <li key={node} className="flex items-center gap-2">
              {st === "done" ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              ) : st === "started" || (!st && !done) ? (
                <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
              ) : st === "failed" ? (
                <Circle className="h-4 w-4 text-red-600" />
              ) : (
                <Circle className="h-4 w-4 text-slate-300" />
              )}
              <span className={st === "done" ? "" : "text-slate-500"}>
                {st === "done" ? "✓ " : st === "failed" ? "✗ " : "○ "}{LABELS[node]}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

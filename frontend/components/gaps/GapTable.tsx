import { Badge } from "@/components/ui/badge";
import type { SkillGapResult } from "@/lib/schemas";

function tone(c: string): "red" | "amber" | "green" {
  if (c === "High") return "red";
  if (c === "Medium") return "amber";
  return "green";
}

export function GapTable({ gap }: { gap: SkillGapResult }) {
  return (
    <div className="grid gap-4">
      <div className="rounded-lg border border-slate-200 p-4">
        <h3 className="font-semibold">Strong ({gap.strong.length})</h3>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {gap.strong.map((s) => <Badge key={s} tone="green">{s}</Badge>)}
          {gap.strong.length === 0 && <span className="text-sm text-slate-500">—</span>}
        </div>
        <h3 className="mt-4 font-semibold">Partial ({gap.partial.length})</h3>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {gap.partial.map((s) => <Badge key={s} tone="amber">{s}</Badge>)}
          {gap.partial.length === 0 && <span className="text-sm text-slate-500">—</span>}
        </div>
      </div>
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left">
            <tr>
              <th className="p-2">Missing skill</th>
              <th className="p-2">Criticality</th>
              <th className="p-2">Why</th>
              <th className="p-2">Weeks</th>
            </tr>
          </thead>
          <tbody>
            {gap.missing.map((m) => (
              <tr key={m.skill} className="border-t border-slate-100">
                <td className="p-2 font-medium">{m.skill}</td>
                <td className="p-2"><Badge tone={tone(m.criticality)}>{m.criticality}</Badge></td>
                <td className="p-2 text-slate-600">{m.reason}</td>
                <td className="p-2 tabular-nums">{m.weeks_to_learn}</td>
              </tr>
            ))}
            {gap.missing.length === 0 && (
              <tr><td colSpan={4} className="p-3 text-slate-500">No missing skills — strong match.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {gap.critical_missing.length > 0 && (
        <p className="text-sm text-slate-600">
          Critical: {gap.critical_missing.join(", ")} — click through to the Roadmap tab weeks covering each skill.
        </p>
      )}
    </div>
  );
}

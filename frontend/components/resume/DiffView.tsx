import { Badge } from "@/components/ui/badge";
import type { ValidationResult } from "@/lib/schemas";

export function DiffView({
  resume,
  validation,
}: {
  resume: Record<string, unknown> | null | undefined;
  validation: ValidationResult | null | undefined;
}) {
  if (!resume) return <p className="text-sm text-slate-500">Optimized resume not ready yet.</p>;
  const skills = (resume.skills as string[]) ?? [];
  const bullets = (resume.bullets as string[]) ?? [];
  const upskill = (resume.upskill as string[]) ?? [];
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="flex items-center gap-2">
        <h3 className="font-semibold">Optimized resume (diff view)</h3>
        {validation && (
          <Badge tone={validation.status === "PASS" ? "green" : "red"}>{validation.status}</Badge>
        )}
      </div>
      {resume.summary != null && <p className="mt-2 text-sm">{String(resume.summary)}</p>}
      <h4 className="mt-3 text-sm font-semibold">Skills</h4>
      <div className="mt-1 flex flex-wrap gap-1.5">
        {skills.map((s) => (
          <Badge key={s} tone={s.startsWith("Areas to Upskill") ? "amber" : "blue"}>{s}</Badge>
        ))}
      </div>
      <h4 className="mt-3 text-sm font-semibold">Rewritten bullets (keywords highlighted)</h4>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
        {bullets.map((b, i) => (
          <li key={i} dangerouslySetInnerHTML={{ __html: highlight(b) }} />
        ))}
      </ul>
      {upskill.length > 0 && (
        <div className="mt-3 rounded-md bg-amber-50 p-2 text-sm">
          <strong>Areas to Upskill (never faked as experience):</strong> {upskill.join(", ")}
        </div>
      )}
      {validation && validation.issues.length > 0 && (
        <ul className="mt-2 text-sm text-red-700">
          {validation.issues.map((iss, i) => (
            <li key={i}>[{iss.type}] {iss.detail}</li>
          ))}
        </ul>
      )}
      <div className="no-print mt-3">
        <button onClick={() => window.print()} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:border-blue-500">
          Print / save report
        </button>
      </div>
    </div>
  );
}

function highlight(text: string): string {
  // naive keyword highlight for demo (backend returns plain text)
  return text.replace(/([A-Za-z][A-Za-z.+#]{2,})/g, "<mark>$1</mark>");
}

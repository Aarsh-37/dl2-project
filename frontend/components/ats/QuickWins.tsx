import { Zap } from "lucide-react";
import type { ATSResult } from "@/lib/schemas";

export function QuickWins({ result }: { result: ATSResult }) {
  const wins = result.quick_wins?.slice(0, 3) ?? [];
  if (!wins.length) return null;
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
      <h3 className="flex items-center gap-1 text-sm font-semibold"><Zap className="h-4 w-4" /> Top-3 quick wins</h3>
      <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
        {wins.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ol>
      {result.improvements?.length > 0 && (
        <details className="mt-2 text-sm">
          <summary className="cursor-pointer text-blue-600">All improvements</summary>
          <ul className="mt-1 list-disc pl-5">
            {result.improvements.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import { mockAnswerRequest } from "@/lib/api";
import { Button } from "@/components/ui/button";

export function MockPanel({ jobId }: { jobId: string }) {
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ scores: Record<string, number>; feedback: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (answer.trim().length < 10) {
      setError("Write at least a sentence before submitting.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const r = await mockAnswerRequest({ job_id: jobId, question_id: "q1", answer });
      setResult(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <h3 className="font-semibold">Mock interview — try an answer</h3>
      <p className="text-xs text-slate-500">POST /mock/answer (on-demand, NOT a graph node)</p>
      <textarea
        className="mt-2 h-28 w-full rounded-md border border-slate-300 p-2 text-sm"
        placeholder="Pick a question above and type your answer…"
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
      />
      <Button onClick={submit} disabled={loading} className="mt-2">
        {loading ? "Scoring…" : "Submit answer"}
      </Button>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {result && (
        <div className="mt-3 text-sm">
          <div className="flex flex-wrap gap-2">
            {Object.entries(result.scores).map(([k, v]) => (
              <span key={k} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">{k}: {v}/5</span>
            ))}
          </div>
          <p className="mt-2 rounded-md bg-slate-50 p-2">{result.feedback}</p>
        </div>
      )}
    </div>
  );
}

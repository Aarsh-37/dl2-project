"use client";

import { use, useState } from "react";
import { ProgressHeader } from "@/components/progress/ProgressHeader";
import { AtsScore } from "@/components/ats/AtsScore";
import { QuickWins } from "@/components/ats/QuickWins";
import { GapTable } from "@/components/gaps/GapTable";
import { Timeline } from "@/components/roadmap/Timeline";
import { QaAccordion } from "@/components/interview/QaAccordion";
import { MockPanel } from "@/components/interview/MockPanel";
import { DiffView } from "@/components/resume/DiffView";
import { ApprovalBar } from "@/components/resume/ApprovalBar";
import { TraceView } from "@/components/verbose/TraceView";
import { Skeleton } from "@/components/ui/skeleton";
import { useResult, useInvalidateResult } from "@/lib/useAnalysis";
import { useStream } from "@/lib/useStream";

const TABS = ["ATS", "Gaps", "Roadmap", "Interview", "Resume", "Verbose"] as const;

export default function ResultsPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params);
  const [tab, setTab] = useState<(typeof TABS)[number]>("ATS");
  const invalidate = useInvalidateResult();
  const { events, done, error: streamError, percent } = useStream(jobId, { onDone: () => invalidate(jobId) });
  const { data, isLoading, isError, error, refetch } = useResult(jobId);

  const ready = (node: string) => events[node] === "done";

  return (
    <div>
      <h1 className="text-2xl font-bold">Step 2 — Career analysis</h1>
      <div className="mt-4">
        <ProgressHeader events={events} percent={percent} done={done} />
      </div>
      {streamError && (
        <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
          Stream interrupted: {streamError} — completed tabs stay interactive.{" "}
          <button className="underline" onClick={() => refetch()}>Retry</button>
        </div>
      )}
      {data?.status === "partial" && (
        <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
          Partial result — some nodes failed. Finished sections are shown; failed ones offer Retry.
        </div>
      )}
      <div className="no-print mt-4 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${
              tab === t ? "bg-blue-600 text-white" : "border border-slate-300 hover:border-blue-500"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="mt-4">
        {isLoading && <Skeleton lines={6} />}
        {isError && (
          <div className="rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-700">
            {(error as Error).message}{" "}
            <button className="underline" onClick={() => refetch()}>Retry</button>
          </div>
        )}
        {data && (
          <>
            {tab === "ATS" && (
              <div className="grid gap-4">
                {!ready("ats_engine") && !data.ats_result ? (
                  <Skeleton lines={4} label="ATS engine scoring…" />
                ) : (
                  data.ats_result && (
                    <>
                      <AtsScore result={data.ats_result} />
                      <QuickWins result={data.ats_result} />
                    </>
                  )
                )}
              </div>
            )}
            {tab === "Gaps" && (
              !ready("skill_gap") && !data.skill_gap ? <Skeleton lines={4} label="Comparing skills…" />
              : data.skill_gap ? <GapTable gap={data.skill_gap} /> : <EmptyMsg />
            )}
            {tab === "Roadmap" && (
              !ready("roadmap") && !data.roadmap ? <Skeleton lines={5} label="Building roadmap…" />
              : data.roadmap ? <Timeline roadmap={data.roadmap} jobId={jobId} /> : <EmptyMsg />
            )}
            {tab === "Interview" && (
              !ready("interview") && !data.interview_questions ? <Skeleton lines={5} label="Preparing interview Qs…" />
              : data.interview_questions ? (
                <div className="grid gap-6">
                  <SourceChips sources={data.interview_questions.sources} />
                  <QaAccordion technical={data.interview_questions.technical} hr={data.interview_questions.hr} />
                  <MockPanel jobId={jobId} />
                </div>
              ) : <EmptyMsg />
            )}
            {tab === "Resume" && (
              !ready("optimizer") && !data.optimized_resume ? <Skeleton lines={5} label="Optimizing resume…" />
              : (
                <div className="grid gap-4">
                  <DiffView resume={data.optimized_resume} validation={data.validation_result} />
                  <ApprovalBar jobId={jobId} />
                </div>
              )
            )}
            {tab === "Verbose" && <TraceView trace={data.agent_trace} />}
          </>
        )}
      </div>
    </div>
  );
}

function EmptyMsg() {
  return <p className="text-sm text-slate-500">Nothing here yet — the node may still be running.</p>;
}

function SourceChips({ sources }: {
  sources?: { source: string; skill: string; page: number | null }[] | null;
}) {
  if (!sources?.length) return null;
  const seen = new Set<string>();
  const uniq = sources.filter((s) => {
    const k = `${s.source}|${s.skill}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
      <span className="font-semibold">Grounded in your prep material: </span>
      {uniq.map((s, i) => (
        <span key={i} className="mr-2 inline-block rounded bg-white px-2 py-0.5 ring-1 ring-slate-200">
          {s.source.replace(".pdf", "")}{s.skill ? ` · ${s.skill}` : ""}{s.page ? ` · p.${s.page}` : ""}
        </span>
      ))}
    </div>
  );
}


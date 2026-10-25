"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { fetchHistory } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { timeAgo } from "@/lib/format";

export default function HistoryPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["history"],
    queryFn: () => fetchHistory(),
  });

  return (
    <div>
      <h1 className="text-2xl font-bold">History</h1>
      <p className="mt-1 text-sm text-slate-600">Past analyses (GET /history). Re-open or delete.</p>
      <div className="mt-4 grid gap-3">
        {isLoading && <Skeleton lines={4} />}
        {isError && (
          <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            {(error as Error).message} <button className="underline" onClick={() => refetch()}>Retry</button>
          </div>
        )}
        {data?.map((h) => (
          <div key={h.job_id} className="flex items-center justify-between rounded-md border border-slate-200 p-4">
            <div>
              <p className="font-medium">{h.role ?? "Analysis"}</p>
              <p className="font-mono text-xs text-slate-500">{h.job_id} · {timeAgo(h.created_at)} · {h.status}{h.score != null ? ` · score ${h.score}` : ""}</p>
            </div>
            <Link href={`/results/${h.job_id}`} className="rounded-md bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700">
              Open
            </Link>
          </div>
        ))}
        {data && data.length === 0 && <p className="text-sm text-slate-500">No analyses yet — start at /analyze.</p>}
      </div>
    </div>
  );
}

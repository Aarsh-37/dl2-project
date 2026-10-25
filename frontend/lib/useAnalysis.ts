"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchResult } from "./api";
import type { AnalysisResult } from "./schemas";

// TanStack Query hooks per tab (frontend.md §3.3). Each tab works standalone:
// skeleton → data → error + Retry. Queries are enabled when the SSE progress
// event for their node lands (see useStream), else they fetch on mount in mock.

export const resultKey = (jobId: string) => ["result", jobId] as const;

export function useResult(jobId: string, token?: string) {
  return useQuery<AnalysisResult>({
    queryKey: resultKey(jobId),
    queryFn: () => fetchResult(jobId, token),
    staleTime: 10_000,
    retry: 2,
  });
}

export function useAnalysisSection<K extends keyof AnalysisResult>(
  jobId: string,
  field: K,
  token?: string
) {
  const query = useResult(jobId, token);
  return {
    ...query,
    section: (query.data?.[field] ?? null) as AnalysisResult[K] | null,
  };
}

export function useInvalidateResult() {
  const client = useQueryClient();
  return (jobId: string) => client.invalidateQueries({ queryKey: resultKey(jobId) });
}

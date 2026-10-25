"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { streamUrl } from "./api";

export type NodeStatus = "started" | "done" | "failed";
export type ProgressEvent = { node: string; status: NodeStatus };

// fetch-SSE hook (frontend.md §3.3, contracts.md §5): single ReadableStream per
// jobId. Parses `event: <name>` / `data: <json>` frames. No EventSource (can't
// set headers), no Vercel proxy by default.

const NODES = [
  "resume_analyzer",
  "jd_analyzer",
  "ats_engine",
  "skill_gap",
  "roadmap",
  "interview",
  "optimizer",
  "validator",
  "coach",
];

export function useStream(jobId: string, opts?: { token?: string; onDone?: () => void }) {
  const [events, setEvents] = useState<Record<string, NodeStatus>>({});
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [approvalOpen, setApprovalOpen] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const mark = useCallback((node: string, status: NodeStatus) => {
    setEvents((prev) => ({ ...prev, [node]: status }));
  }, []);

  useEffect(() => {
    if (!jobId) return;
    setEvents({});
    setDone(false);
    setError(null);

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    (async () => {
      try {
        const res = await fetch(streamUrl(jobId, opts?.token), {
          headers: opts?.token ? { Authorization: `Bearer ${opts.token}` } : {},
          signal: ctrl.signal,
        });
        if (!res.ok || !res.body) throw new Error(`Stream failed (${res.status})`);
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        let currentEvent = "progress";
        for (;;) {
          const { done: rd, value } = await reader.read();
          if (rd) break;
          buf += decoder.decode(value, { stream: true });
          const frames = buf.split("\n\n");
          buf = frames.pop() ?? "";
          for (const frame of frames) {
            for (const line of frame.split("\n")) {
              if (line.startsWith("event:")) currentEvent = line.slice(6).trim();
              else if (line.startsWith("data:")) {
                const payload = JSON.parse(line.slice(5).trim());
                if (currentEvent === "progress") mark(payload.node, payload.status);
                else if (currentEvent === "interrupt" && payload.type === "resume_approval")
                  setApprovalOpen(true);
                else if (currentEvent === "done") {
                  setDone(true);
                  opts?.onDone?.();
                } else if (currentEvent === "error") setError(payload.message ?? "Stream error");
                currentEvent = "progress";
              }
            }
          }
        }
      } catch (e) {
        if ((e as Error).name !== "AbortError") setError((e as Error).message);
      }
    })();
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const completed = NODES.filter((n) => events[n] === "done").length;
  const percent = Math.round((completed / NODES.length) * 100);

  return { events, done, error, approvalOpen, setApprovalOpen, completed, percent, nodes: NODES };
}

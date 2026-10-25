"use client";

import { useState } from "react";
import { approveResumeRequest, exportResumeRequest, type ExportFormat } from "@/lib/api";
import { useStore } from "@/lib/store";
import { Button } from "@/components/ui/button";

export function ApprovalBar({ jobId }: { jobId: string }) {
  const note = useStore((s) => s.approvalNote);
  const setNote = useStore((s) => s.setApprovalNote);
  const [state, setState] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState<ExportFormat | null>(null);

  async function act(approved: boolean) {
    setLoading(true);
    try {
      await approveResumeRequest({ job_id: jobId, approved, note });
      setState(approved ? "Approved ✓ — resume stamped for download." : "Change requested — optimizer will regenerate (≤2 retries).");
    } catch (e) {
      setState(`Failed: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  async function download(format: ExportFormat) {
    setDownloading(format);
    try {
      await exportResumeRequest({ job_id: jobId, format });
      setState(`${format.toUpperCase()} downloaded — compiled from your tailored LaTeX resume.`);
    } catch (e) {
      setState(`Download failed: ${(e as Error).message}`);
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="no-print rounded-lg border border-slate-200 p-4">
      <h3 className="font-semibold">Human approval (HITL)</h3>
      <p className="text-xs text-slate-500">
        Approve the tailored resume, or request changes before exporting.
      </p>
      <textarea
        className="mt-2 h-20 w-full rounded-md border border-slate-300 p-2 text-sm"
        placeholder="Edit note (optional) — e.g. 'keep 1-page, move skills up'…"
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />
      <div className="mt-2 flex gap-2">
        <Button onClick={() => act(true)} disabled={loading}>Approve</Button>
        <button
          onClick={() => act(false)}
          disabled={loading}
          className="rounded-md border border-slate-300 px-4 py-2 text-sm hover:border-amber-500"
        >
          Request changes
        </button>
      </div>
      <div className="mt-3 border-t border-slate-100 pt-3">
        <p className="text-xs font-medium text-slate-500">Download tailored resume</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {(["pdf", "tex", "docx"] as const).map((fmt) => (
            <button
              key={fmt}
              onClick={() => download(fmt)}
              disabled={downloading !== null}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-700 disabled:opacity-50"
            >
              {downloading === fmt ? "Preparing…" : fmt === "pdf" ? "Download PDF" : fmt === "tex" ? "Download LaTeX" : "Download DOCX"}
            </button>
          ))}
        </div>
      </div>
      {state && <p className="mt-2 text-sm">{state}</p>}
    </div>
  );
}

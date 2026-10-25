"use client";

import { useCallback, useState } from "react";
import { Upload, FileText } from "lucide-react";
import { resumeFileSchema } from "@/lib/schemas";

export function UploadCard({
  file,
  onFile,
  resumeText,
  onText,
}: {
  file: File | null;
  onFile: (f: File | null) => void;
  resumeText: string;
  onText: (t: string) => void;
}) {
  const [err, setErr] = useState<string | null>(null);

  const pick = useCallback(
    (f: File | undefined) => {
      if (!f) return;
      const parsed = resumeFileSchema.safeParse(f);
      if (!parsed.success) {
        setErr(parsed.error.issues[0]?.message ?? "Invalid file");
        return;
      }
      setErr(null);
      onFile(f);
    },
    [onFile]
  );

  return (
    <div className="rounded-lg border border-slate-200 p-5">
      <h2 className="font-semibold">Resume</h2>
      <div
        className="mt-3 rounded-md border-2 border-dashed border-slate-300 p-6 text-center"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          pick(e.dataTransfer.files?.[0]);
        }}
      >
        <Upload className="mx-auto h-6 w-6 text-slate-400" />
        <p className="mt-2 text-sm">Drag & drop your resume here, or</p>
        <label className="mt-2 inline-block cursor-pointer rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:border-blue-500">
          Browse file
          <input
            type="file"
            className="hidden"
            accept=".pdf,.doc,.docx,.txt"
            onChange={(e) => pick(e.target.files?.[0])}
          />
        </label>
        {file && (
          <p className="mt-2 flex items-center justify-center gap-1 text-sm text-slate-700">
            <FileText className="h-4 w-4" /> {file.name} ({Math.round(file.size / 1024)} KB)
            <button className="ml-2 underline" onClick={() => onFile(null)}>Remove</button>
          </p>
        )}
        {err && <p className="mt-2 text-sm text-red-600">{err}</p>}
        <p className="mt-1 text-xs text-slate-500">PDF / DOCX / TXT · ≤ 5MB</p>
      </div>
      <details className="mt-3">
        <summary className="cursor-pointer text-sm text-blue-600">Or paste resume text (scanned-PDF fallback)</summary>
        <textarea
          className="mt-2 h-32 w-full rounded-md border border-slate-300 p-2 text-sm"
          placeholder="Paste resume text here…"
          value={resumeText}
          onChange={(e) => onText(e.target.value)}
        />
      </details>
    </div>
  );
}

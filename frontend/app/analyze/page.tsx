"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { UploadCard } from "@/components/analyze/UploadCard";
import { JdForm } from "@/components/analyze/JdForm";
import { analyzeRequest } from "@/lib/api";
import { useStore } from "@/lib/store";
import type { AnalyzeFormValues } from "@/lib/schemas";

export default function AnalyzePage() {
  const router = useRouter();
  const { draft } = useStore();
  const [file, setFile] = useState<File | null>(null);
  const [resumeText, setResumeText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(values: AnalyzeFormValues) {
    setLoading(true);
    setError(null);
    try {
      if (!file && resumeText.trim().length < 50) {
        throw new Error("Upload a resume file or paste at least 50 characters of resume text.");
      }
      const { job_id } = await analyzeRequest({
        file,
        resume_text: resumeText || undefined,
        jd_text: values.jd_text,
        hours_per_day: values.hours_per_day,
      });
      useStore.getState().setJobId(job_id);
      router.push(`/results/${job_id}`);
    } catch (e) {
      setError((e as Error).message ?? "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-bold">Step 1 — Upload resume + job description</h1>
      <div className="mt-6 grid gap-6">
        <UploadCard file={file} onFile={setFile} resumeText={resumeText} onText={setResumeText} />
        <JdForm
          key={JSON.stringify(draft)}
          defaultValues={draft}
          loading={loading}
          onSubmit={onSubmit}
        />
        {error && (
          <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            {error}{" "}
            <button className="underline" onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}
      </div>
    </div>
  );
}

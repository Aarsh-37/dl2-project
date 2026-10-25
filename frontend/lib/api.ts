import { analysisResultSchema, type AnalysisResult } from "./schemas";

export type ApiError = { message: string; status?: number; job_id?: string };

function apiBase(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";
}

async function parseJson(res: Response): Promise<unknown> {
  const text = await res.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    throw { message: `Invalid JSON from server (${res.status})`, status: res.status } satisfies ApiError;
  }
}

export async function analyzeRequest(args: {
  file?: File | null;
  resume_text?: string;
  jd_text: string;
  hours_per_day?: number;
  token?: string;
}): Promise<{ job_id: string; stream_url: string }> {
  const form = new FormData();
  if (args.file) form.append("resume_file", args.file);
  if (args.resume_text) form.append("resume_text", args.resume_text);
  form.append("jd_text", args.jd_text);
  if (args.hours_per_day != null) form.append("hours_per_day", String(args.hours_per_day));

  const res = await fetch(`${apiBase()}/analyze`, {
    method: "POST",
    body: form,
    headers: args.token ? { Authorization: `Bearer ${args.token}` } : {},
  });
  const data = (await parseJson(res)) as { job_id: string; stream_url: string; detail?: string };
  if (!res.ok) throw { message: data.detail ?? `Analyze failed (${res.status})`, status: res.status } satisfies ApiError;
  return data;
}

export async function fetchResult(jobId: string, token?: string): Promise<AnalysisResult> {
  const res = await fetch(`${apiBase()}/result/${jobId}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    cache: "no-store",
  });
  const data = await parseJson(res);
  if (!res.ok)
    throw {
      message: (data as { detail?: string }).detail ?? `Result fetch failed (${res.status})`,
      status: res.status,
    } satisfies ApiError;
  return analysisResultSchema.parse(data);
}

export async function mockAnswerRequest(args: {
  job_id: string;
  question_id: string;
  answer: string;
  token?: string;
}): Promise<{ scores: Record<string, number>; feedback: string }> {
  const res = await fetch(`${apiBase()}/mock/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(args.token ? { Authorization: `Bearer ${args.token}` } : {}) },
    body: JSON.stringify({ job_id: args.job_id, question_id: args.question_id, answer: args.answer }),
  });
  const data = await parseJson(res);
  if (!res.ok)
    throw {
      message: (data as { detail?: string }).detail ?? `Mock eval failed (${res.status})`,
      status: res.status,
    } satisfies ApiError;
  return data as { scores: Record<string, number>; feedback: string };
}

export async function approveResumeRequest(args: {
  job_id: string;
  approved: boolean;
  note?: string;
  token?: string;
}): Promise<{ ok: boolean }> {
  const res = await fetch(`${apiBase()}/resumes/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(args.token ? { Authorization: `Bearer ${args.token}` } : {}) },
    body: JSON.stringify({ job_id: args.job_id, approved: args.approved, note: args.note ?? "" }),
  });
  if (!res.ok) throw { message: `Approve failed (${res.status})`, status: res.status } satisfies ApiError;
  return { ok: true };
}

export async function fetchHistory(token?: string): Promise<
  { job_id: string; created_at: string; role?: string; score?: number; status: string }[]
> {
  const res = await fetch(`${apiBase()}/history`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    cache: "no-store",
  });
  const data = (await parseJson(res)) as { items?: unknown };
  if (!res.ok) throw { message: `History failed (${res.status})`, status: res.status } satisfies ApiError;
  return (data.items ?? []) as { job_id: string; created_at: string; role?: string; score?: number; status: string }[];
}

export function streamUrl(jobId: string, token?: string): string {
  // Client calls FastAPI directly (contracts.md §5) — no Vercel SSE proxy by default.
  const base = apiBase();
  return token ? `${base}/stream/${jobId}?token=${encodeURIComponent(token)}` : `${base}/stream/${jobId}`;
}

export type ExportFormat = "pdf" | "tex" | "docx";

const EXPORT_MIME: Record<ExportFormat, string> = {
  pdf: "application/pdf",
  tex: "text/x-tex",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
};

/** Download the tailored resume (LaTeX-compiled PDF, .tex source, or DOCX). */
export async function exportResumeRequest(args: {
  job_id: string;
  format: ExportFormat;
  token?: string;
}): Promise<void> {
  const res = await fetch(`${apiBase()}/resumes/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(args.token ? { Authorization: `Bearer ${args.token}` } : {}) },
    body: JSON.stringify({ job_id: args.job_id, format: args.format }),
  });
  if (!res.ok) {
    const data = (await parseJson(res).catch(() => ({}))) as { detail?: string };
    throw { message: data.detail ?? `Export failed (${res.status})`, status: res.status } satisfies ApiError;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(new Blob([blob], { type: EXPORT_MIME[args.format] }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `resume-${args.job_id.slice(0, 8)}.${args.format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

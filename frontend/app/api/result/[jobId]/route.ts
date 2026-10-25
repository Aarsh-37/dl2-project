import { NextRequest, NextResponse } from "next/server";

// Proxy → FastAPI GET /result/{job_id}. Same-origin option; direct fetchResult()
// against NEXT_PUBLIC_API_URL is the default (frontend.md §3.5).

export async function GET(_req: NextRequest, { params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";
  const auth = _req.headers.get("authorization");
  const res = await fetch(`${base}/result/${jobId}`, {
    headers: auth ? { Authorization: auth } : {},
    cache: "no-store",
  });
  const data = await res.text();
  return new NextResponse(data, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
  });
}

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";
  const auth = _req.headers.get("authorization");
  const res = await fetch(`${base}/result/${jobId}`, {
    method: "DELETE",
    headers: auth ? { Authorization: auth } : {},
  });
  const data = await res.text();
  return new NextResponse(data, { status: res.status });
}

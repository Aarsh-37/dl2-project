import { NextRequest, NextResponse } from "next/server";

// Proxy → FastAPI POST /analyze (hides backend URL, attaches JWT if present).
// Client normally calls FastAPI directly for SSE; this proxy exists for the
// multipart upload path when callers prefer same-origin.

export async function POST(req: NextRequest) {
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";
  const form = await req.formData();
  const auth = req.headers.get("authorization");
  const res = await fetch(`${base}/analyze`, {
    method: "POST",
    body: form,
    headers: auth ? { Authorization: auth } : {},
  });
  const data = await res.text();
  return new NextResponse(data, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
  });
}

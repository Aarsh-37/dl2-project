"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { useStore } from "@/lib/store";
import type { InterviewItem } from "@/lib/schemas";

function Item({ item }: { item: InterviewItem }) {
  const quizMode = useStore((s) => s.quizMode);
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-md border border-slate-200 p-3">
      <button className="w-full text-left" onClick={() => setOpen((o) => !o)}>
        <span className="font-medium">{item.q}</span>
      </button>
      <div className="mt-1 flex gap-1.5">
        <Badge tone="blue">{item.difficulty}</Badge>
        <span className="text-xs text-slate-500">Why asked: {item.why_asked}</span>
      </div>
      {open && (
        <div className={`mt-2 text-sm ${quizMode ? "select-none blur-sm hover:blur-0" : ""}`}>
          <p><strong>Ideal answer:</strong> {item.ideal_answer}</p>
          <ul className="mt-1 list-disc pl-5">
            {item.key_points.map((k) => <li key={k}>{k}</li>)}
          </ul>
          <p className="mt-1 text-slate-600"><strong>Follow-up:</strong> {item.follow_up}</p>
        </div>
      )}
    </div>
  );
}

export function QaAccordion({ technical, hr }: { technical: InterviewItem[]; hr: InterviewItem[] }) {
  const quizMode = useStore((s) => s.quizMode);
  const setQuizMode = useStore((s) => s.setQuizMode);
  return (
    <div>
      <label className="no-print flex items-center gap-2 text-sm">
        <input type="checkbox" checked={quizMode} onChange={(e) => setQuizMode(e.target.checked)} />
        Quiz mode (blur answers until hover)
      </label>
      <h3 className="mt-3 font-semibold">Technical ({technical.length})</h3>
      <div className="mt-2 grid gap-2">
        {technical.map((q, i) => <Item key={i} item={q} />)}
      </div>
      <h3 className="mt-4 font-semibold">HR / Behavioral ({hr.length})</h3>
      <div className="mt-2 grid gap-2">
        {hr.map((q, i) => <Item key={i} item={q} />)}
      </div>
    </div>
  );
}

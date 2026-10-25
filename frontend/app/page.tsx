import Link from "next/link";
import { FileSearch, ListChecks, Map, MessagesSquare, FileEdit } from "lucide-react";

const FEATURES = [
  { icon: FileSearch, title: "ATS score as per JD", desc: "Deterministic engine scores; LLM explains strengths, gaps, quick wins." },
  { icon: ListChecks, title: "Missing skills", desc: "Strong / Partial / Missing × Required / Preferred with criticality." },
  { icon: Map, title: "Learning roadmap", desc: "7/14/30/60/90-day plan with RAG resources, projects, checkpoints." },
  { icon: MessagesSquare, title: "Interview prep + mock", desc: "Tech + HR Q&A grounded in your resume, plus on-demand scoring." },
  { icon: FileEdit, title: "Resume rewrite + validation", desc: "Constrained optimizer, hallucination gate, human approve/edit." },
];

export default function LandingPage() {
  return (
    <div>
      <section className="py-10 text-center">
        <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl">
          From Resume to Offer — <span className="text-blue-600">Autopilot Your Career</span>
        </h1>
        <div className="mt-6 flex justify-center gap-3">
          <Link href="/analyze" className="rounded-md bg-blue-600 px-5 py-2.5 font-medium text-white hover:bg-blue-700">
            Analyze resume
          </Link>
          <Link href="/history" className="rounded-md border border-slate-300 px-5 py-2.5 font-medium hover:border-blue-500">
            View history
          </Link>
        </div>
      </section>
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f) => (
          <div key={f.title} className="rounded-lg border border-slate-200 p-5">
            <f.icon className="h-6 w-6 text-blue-600" />
            <h3 className="mt-2 font-semibold">{f.title}</h3>
            <p className="mt-1 text-sm text-slate-600">{f.desc}</p>
          </div>
        ))}
      </section>
    </div>
  );
}

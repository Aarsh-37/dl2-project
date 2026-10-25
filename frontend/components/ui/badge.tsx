import { clsx } from "clsx";

export function Badge({ children, tone = "slate" }: { children: React.ReactNode; tone?: "slate" | "green" | "amber" | "red" | "blue" }) {
  const tones: Record<string, string> = {
    slate: "bg-slate-100 text-slate-700",
    green: "bg-emerald-100 text-emerald-800",
    amber: "bg-amber-100 text-amber-800",
    red: "bg-red-100 text-red-800",
    blue: "bg-blue-100 text-blue-800",
  };
  return (
    <span className={clsx("inline-block rounded-full px-2 py-0.5 text-xs font-medium", tones[tone])}>
      {children}
    </span>
  );
}

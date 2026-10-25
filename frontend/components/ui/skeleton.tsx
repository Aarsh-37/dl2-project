export function Skeleton({ lines = 3, label }: { lines?: number; label?: string }) {
  return (
    <div className="animate-pulse rounded-md border border-slate-200 p-4" aria-label={label ?? "Loading"}>
      {label && <p className="mb-2 text-xs text-slate-500">{label}</p>}
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="mb-2 h-4 rounded bg-slate-200" style={{ width: `${90 - i * 12}%` }} />
      ))}
    </div>
  );
}

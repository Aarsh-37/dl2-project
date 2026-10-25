"use client";

import { useState } from "react";
import type { Roadmap, RoadmapDay } from "@/lib/schemas";

export function Timeline({ roadmap, jobId }: { roadmap: Roadmap; jobId: string }) {
  const weeks = roadmap.weeks;
  const [checked, setChecked] = useState<Record<string, boolean>>(() => {
    try {
      return JSON.parse(localStorage.getItem(`roadmap-${jobId}`) ?? "{}");
    } catch {
      return {};
    }
  });

  function toggle(key: string) {
    setChecked((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      try {
        localStorage.setItem(`roadmap-${jobId}`, JSON.stringify(next));
      } catch { /* private mode */ }
      return next;
    });
  }

  if (!weeks.length)
    return (
      <p className="rounded-lg border border-slate-200 p-4 text-sm text-slate-600">
        No missing skills — nothing to schedule. Your roadmap is already complete.
      </p>
    );

  return (
    <div className="grid gap-4">
      {(roadmap.time_allocation?.length || roadmap.total_days) && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm">
          <strong>
            {roadmap.total_days ? `${roadmap.total_days}-day plan` : "Study plan"}
          </strong>
          {roadmap.time_allocation?.length ? (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-left text-xs sm:text-sm">
                <thead>
                  <tr className="text-slate-500">
                    <th className="py-1 pr-4 font-medium">Daily time allocation</th>
                    <th className="py-1 font-medium">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {roadmap.time_allocation.map((a) => (
                    <tr key={a.activity} className="border-t border-blue-100">
                      <td className="py-1 pr-4">{a.activity}</td>
                      <td className="py-1 tabular-nums">{a.time}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      )}
      {weeks.map((w) => (
        <div key={w.week} className="rounded-lg border border-slate-200 p-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold">Week {w.week} — {w.focus}</h3>
            <span className="text-xs text-slate-500">{w.hours}h</span>
          </div>
          {w.days?.length ? (
            <div className="mt-3 grid gap-3">
              {w.days.map((d) => (
                <DayCard key={d.day} day={d} checked={checked} toggle={toggle} />
              ))}
            </div>
          ) : (
            <ul className="mt-2 space-y-1 text-sm">
              {w.tasks.map((t) => (
                <li key={t} className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={!!checked[`w${w.week}:${t}`]}
                    onChange={() => toggle(`w${w.week}:${t}`)}
                    aria-label={`${t} done`}
                  />
                  <span className={checked[`w${w.week}:${t}`] ? "line-through text-slate-400" : ""}>{t}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-sm"><strong>Resources:</strong>{" "}
            {w.resources.map((r, i) => (
              <span key={r.url}>
                {i > 0 && " · "}
                <a className="text-blue-600 underline" href={r.url} target="_blank" rel="noreferrer">{r.title}</a>
              </span>
            ))}
          </p>
          <p className="mt-1 text-sm"><strong>Mini-project:</strong> {w.project}</p>
          <p className="mt-1 text-sm text-slate-600"><strong>Checkpoint:</strong> {w.checkpoint}</p>
        </div>
      ))}
    </div>
  );
}

function DayCard({ day, checked, toggle }: {
  day: RoadmapDay;
  checked: Record<string, boolean>;
  toggle: (key: string) => void;
}) {
  const done = !!checked[`d${day.day}`];
  return (
    <div className={`rounded-md border p-3 ${done ? "border-green-200 bg-green-50/50" : "border-slate-100 bg-slate-50/60"}`}>
      <div className="flex items-start gap-2">
        <input
          type="checkbox"
          className="mt-1"
          checked={done}
          onChange={() => toggle(`d${day.day}`)}
          aria-label={`Day ${day.day} done`}
        />
        <div className="flex-1">
          <p className={`text-sm font-semibold ${done ? "line-through text-slate-400" : ""}`}>
            Day {day.day} — {day.title}
            <span className="ml-2 text-xs font-normal text-slate-500">{day.hours}h</span>
          </p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-slate-700">
            {day.topics.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
          <p className="mt-1 text-sm text-slate-600">
            <strong>Practice:</strong> {day.practice}
          </p>
          {day.resources?.length ? (
            <p className="mt-1 text-xs text-slate-500">
              {day.resources.map((r, i) => (
                <span key={r.url}>
                  {i > 0 && " · "}
                  <a className="text-blue-600 underline" href={r.url} target="_blank" rel="noreferrer">{r.title}</a>
                </span>
              ))}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

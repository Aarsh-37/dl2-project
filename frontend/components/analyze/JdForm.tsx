"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { analyzeFormSchema, type AnalyzeFormValues } from "@/lib/schemas";
import { useStore } from "@/lib/store";
import { Button } from "@/components/ui/button";

export function JdForm({
  defaultValues,
  loading,
  onSubmit,
}: {
  defaultValues: AnalyzeFormValues;
  loading: boolean;
  onSubmit: (v: AnalyzeFormValues) => void;
}) {
  const { register, handleSubmit, formState: { errors } } = useForm<AnalyzeFormValues>({
    resolver: zodResolver(analyzeFormSchema),
    defaultValues,
  });
  const setDraft = useStore((s) => s.setDraft);

  return (
    <form
      className="rounded-lg border border-slate-200 p-5"
      onSubmit={handleSubmit((v) => {
        setDraft(v);
        onSubmit(v);
      })}
    >
      <h2 className="font-semibold">Job description + preferences</h2>
      <label className="mt-3 block text-sm font-medium" htmlFor="jd_text">Job description *</label>
      <textarea
        id="jd_text"
        className="mt-1 h-40 w-full rounded-md border border-slate-300 p-2 text-sm"
        placeholder="Paste the JD here (≥ 50 characters)…"
        {...register("jd_text")}
      />
      {errors.jd_text && <p className="text-sm text-red-600">{errors.jd_text.message}</p>}

      <div className="mt-3">
        <label className="text-sm font-medium" htmlFor="hours_per_day">Hours / day</label>
        <input id="hours_per_day" type="number" min={1} max={12} className="mt-1 w-full rounded-md border border-slate-300 p-2 text-sm" {...register("hours_per_day")} />
        {errors.hours_per_day && <p className="text-sm text-red-600">{errors.hours_per_day.message}</p>}
      </div>
      <Button type="submit" disabled={loading} className="mt-4">
        {loading ? "Analyzing…" : "Analyze →"}
      </Button>
    </form>
  );
}

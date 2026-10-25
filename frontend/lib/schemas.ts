import { z } from "zod";

// Mirrors backend Pydantic v2 schemas (contracts.md §4). Field names frozen —
// renames require a contract bump. New fields must be optional-nullable.

export const atsResultSchema = z.object({
  score: z.number().min(0).max(100),
  breakdown: z.object({
    keyword: z.number(),
    skill: z.number(),
    // semantic is null until Phase 2 embeddings backfill (renormalized v1)
    semantic: z.number().nullable(),
    experience: z.number(),
    education: z.number(),
    project_relevance: z.number(),
  }),
  verdict: z.string(),
  strengths: z.array(z.string()),
  gaps: z.array(z.string()),
  improvements: z.array(z.string()),
  quick_wins: z.array(z.string()),
  rationale: z.string(),
});
export type ATSResult = z.infer<typeof atsResultSchema>;

export const skillGapItemSchema = z.object({
  skill: z.string(),
  criticality: z.enum(["High", "Medium", "Low"]),
  reason: z.string(),
  weeks_to_learn: z.number(),
});
export type SkillGapItem = z.infer<typeof skillGapItemSchema>;

export const skillGapResultSchema = z.object({
  strong: z.array(z.string()),
  partial: z.array(z.string()),
  missing: z.array(skillGapItemSchema),
  critical_missing: z.array(z.string()),
});
export type SkillGapResult = z.infer<typeof skillGapResultSchema>;

export const roadmapDaySchema = z.object({
  day: z.number(),
  title: z.string(),
  skill: z.string(),
  hours: z.number(),
  topics: z.array(z.string()),
  practice: z.string(),
  resources: z.array(
    z.object({ title: z.string(), url: z.string(), type: z.string().optional() })
  ).optional().default([]),
});
export type RoadmapDay = z.infer<typeof roadmapDaySchema>;

export const roadmapWeekSchema = z.object({
  week: z.number(),
  focus: z.string(),
  hours: z.number(),
  tasks: z.array(z.string()),
  resources: z.array(
    z.object({ title: z.string(), url: z.string(), type: z.string().optional() })
  ),
  project: z.string(),
  checkpoint: z.string(),
  days: z.array(roadmapDaySchema).optional(),
});
export type RoadmapWeek = z.infer<typeof roadmapWeekSchema>;

export const roadmapSchema = z.object({
  weeks: z.array(roadmapWeekSchema),
  time_allocation: z.array(
    z.object({ activity: z.string(), time: z.string() })
  ).optional(),
  total_days: z.number().optional(),
});
export type Roadmap = z.infer<typeof roadmapSchema>;

export const interviewItemSchema = z.object({
  q: z.string(),
  difficulty: z.string(),
  why_asked: z.string(),
  ideal_answer: z.string(),
  key_points: z.array(z.string()),
  follow_up: z.string(),
});
export type InterviewItem = z.infer<typeof interviewItemSchema>;

export const validationResultSchema = z.object({
  status: z.enum(["PASS", "REJECT"]),
  issues: z.array(z.object({ type: z.string(), detail: z.string() })),
});
export type ValidationResult = z.infer<typeof validationResultSchema>;

export const agentTraceSchema = z.object({
  node: z.string(),
  provider: z.string(),
  model: z.string(),
  latency_ms: z.number(),
  mode: z.enum(["live", "error", "disabled"]),
  detail: z.string().optional(),
});
export type AgentTrace = z.infer<typeof agentTraceSchema>;

export const jobMatchSchema = z.object({
  title: z.string(),
  company: z.string(),
  location: z.string(),
  url: z.string().url(),
  source: z.string(),
  match_pct: z.number().min(0).max(100),
  matched_skills: z.array(z.string()),
  salary: z.string().nullable().optional(),
});
export type JobMatch = z.infer<typeof jobMatchSchema>;

// GET /result/{job_id} shape (contracts.md §5.1, abridged)
export const analysisResultSchema = z.object({
  job_id: z.string(),
  status: z.enum(["done", "partial", "queued", "running", "failed"]),
  ats_result: atsResultSchema.nullable(),
  skill_gap: skillGapResultSchema.nullable(),
  roadmap: roadmapSchema.nullable(),
  interview_questions: z
    .object({
      technical: z.array(interviewItemSchema),
      hr: z.array(interviewItemSchema),
      sources: z
        .array(z.object({ source: z.string(), skill: z.string(), page: z.number().nullable() }))
        .optional(),
    })
    .nullable(),
  optimized_resume: z.record(z.string(), z.unknown()).nullable().optional(),
  validation_result: validationResultSchema.nullable(),
  jobs: z.array(jobMatchSchema).nullable(),
  job_matches: z.array(jobMatchSchema).nullable(),
  career_recommendations: z.string().nullable(),
  agent_trace: z.array(agentTraceSchema).nullable().optional(),
  errors: z.array(z.unknown()).optional().default([]),
});
export type AnalysisResult = z.infer<typeof analysisResultSchema>;

// Analyze form (mirrors POST /analyze validation: MIME, 5MB, JD ≥50ch)
export const analyzeFormSchema = z.object({
  jd_text: z.string().min(50, "Job description must be at least 50 characters"),
  hours_per_day: z.coerce.number().min(1).max(12).default(3),
});
export type AnalyzeFormValues = z.infer<typeof analyzeFormSchema>;

export const resumeFileSchema = z
  .instanceof(File)
  .refine((f) => f.size <= 5 * 1024 * 1024, "Resume must be ≤ 5MB")
  .refine(
    (f) =>
      /pdf|msword|officedocument.wordprocessingml.document|plain/.test(f.type) ||
      /\.(pdf|docx?|txt)$/i.test(f.name),
    "Resume must be PDF, DOCX, or TXT"
  );

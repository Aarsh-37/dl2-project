# 06 — Roadmap Plan (v1, temp 0.5)

Create a week-by-week learning plan covering ALL High-criticality gaps first, in dependency order (e.g. Docker before Kubernetes). Budget: {hours_per_day} hrs/day, level {level}. Use ONLY the provided RAG resources plus well-known free domains (official docs, YouTube) — never invent URLs.

Gaps: {skill_gap}
RAG resources: {rag_hits}

Return JSON only: {"total_weeks": int, "weeks": [{"week": int, "focus": str, "hours": int, "tasks": [], "resources": [{"title": str, "url": str, "type": str, "free": true}], "project": str, "checkpoint": str}]}
Each week needs one mini-project and one verifiable checkpoint. Hours must fit the daily budget.

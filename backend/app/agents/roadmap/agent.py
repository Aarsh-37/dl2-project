"""Career Roadmap agent: gaps -> day-wise study plan (temp ~0.4).

Output shape (frontend-safe extension of the frozen week shape):
  {weeks: [{week, focus, hours, tasks, resources, project, checkpoint,
            days: [{day, title, skill, hours, topics[], practice, resources[]}]}],
   time_allocation: [{activity, time}], total_days: int}

Day budgeting scales with the user's daily hours: each missing skill gets
days from its weeks_to_learn, then +1 revision +1 mock +1 final day.
Topics come from your ingested PDF Q&As (RAG) and the question bank;
resources only from the KB allowlist — invented URLs are dropped.
"""
from __future__ import annotations

import re

from app.core.llm import LLMError, get_llm, llm_json
from app.services import kb_service as kb

MAX_WEEKS = 8
MAX_DAYS = 30
MAX_SKILL_DAYS = 4
MAX_SKILL_DAY_TOTAL = 24

PRACTICES = [
    "Explain {skill} in your own words in 2 minutes, aloud, with no notes.",
    "Hands-on: build the smallest working {skill} example and commit it.",
    "Answer 5 {skill} interview questions aloud without reading the answers.",
    "Build-or-break: extend yesterday's example with one new {skill} feature.",
]


def _week_resources(skill: str) -> tuple[list[dict], dict[str, str]]:
    rows = kb.get_resources([skill]).get(skill, [])
    resources = [{"title": r["title"], "url": r["url"], "type": r.get("type", "docs")}
                 for r in rows if r.get("url")][:4]
    return resources, {r["url"]: r["type"] for r in resources}


def _allow_normalize(allowed: dict) -> dict[str, dict[str, str]]:
    """Accept {skill: {url: type}} or legacy {skill: {urls}} sets."""
    norm: dict[str, dict[str, str]] = {}
    for skill, urls in (allowed or {}).items():
        if isinstance(urls, dict):
            norm[skill] = dict(urls)
        else:
            norm[skill] = {u: "docs" for u in (urls or [])}
    return norm


def allocate_days(missing: list[dict], hours_per_day: int) -> list[dict]:
    """Days per skill from effort (weeks_to_learn) scaled by daily hours.

    days = clamp(round(wks * hours / 8), 1, 4): at 4h/day a 2-week skill gets
    1 day and a 4-week skill gets 2 — interview-prep density, matching the
    worked 14-day example (7 topics at ~4h/day).
    """
    hours = max(1, min(12, hours_per_day or 3))
    alloc = [{"skill": m["skill"], "days": max(1, min(MAX_SKILL_DAYS,
               round(m.get("weeks_to_learn", 3) * hours / 8))),
              "criticality": m.get("criticality", "Medium"),
              "weeks_to_learn": m.get("weeks_to_learn", 3)} for m in missing]
    total = sum(a["days"] for a in alloc)
    while total > MAX_SKILL_DAY_TOTAL:  # shrink longest first, keep >= 1
        longest = max(alloc, key=lambda a: a["days"])
        if longest["days"] <= 1:
            break
        longest["days"] -= 1
        total -= 1
    return alloc


def _merged_skill_resources(skills: list[str], cap: int = 4) -> list[dict]:
    """Union of per-skill KB resources (docs + video first) for revision days."""
    merged: list[dict] = []
    seen: set[str] = set()
    per_skill = [kb.get_resources([s]).get(s, []) for s in skills]
    for i in range(max((len(r) for r in per_skill), default=0)):
        for rows in per_skill:
            if i < len(rows) and rows[i]["url"] not in seen:
                seen.add(rows[i]["url"])
                merged.append(rows[i])
                if len(merged) >= cap:
                    return merged
    return merged


def _topic_bank(skill: str) -> list[str]:
    """Fallback day topics: your PDF Q&As first, then bank questions."""
    topics: list[str] = []
    for pair in kb.get_rag_questions([skill], per_skill=6):
        topics.append(f"Study + answer: {pair['q']}")
    for b in kb.get_questions([skill], limit=6):
        q = f"Study + answer: {b.get('q', '')}"
        if b.get("q") and q not in topics:
            topics.append(q)
    return topics


def fallback_day(skill: str, kind: str, day_no: int, hours: int,
                 day_idx: int = 0, topic_pool: list[str] | None = None) -> dict:
    """One deterministic study day. kind: skill|revision|mock|final."""
    resources, _ = _week_resources(skill) if skill else ([], {})
    if kind == "skill":
        pool = topic_pool if topic_pool is not None else _topic_bank(skill)
        topics = pool[:5] or [f"{skill} fundamentals",
                              f"{skill} core concepts",
                              f"{skill} common pitfalls",
                              f"{skill} hands-on example"]
        if len(topics) < 4:
            topics += [f"{skill} guided practice",
                       f"{skill} mini-project milestone"][:4 - len(topics)]
        return {"day": day_no, "title": skill, "skill": skill, "hours": hours,
                "topics": topics[:6],
                "practice": PRACTICES[day_idx % len(PRACTICES)].format(skill=skill),
                "resources": resources}
    if kind == "revision":
        return {"day": day_no, "title": f"Revision ({skill})", "skill": skill,
                "hours": hours, "topics": (topic_pool or [])[:6] or [f"Revise {skill}"],
                "practice": "10-minute mock per topic, no notes; re-study misses.",
                "resources": resources}
    if kind == "mock":
        return {"day": day_no, "title": "Technical Mock Interview", "skill": "",
                "hours": hours, "topics": (topic_pool or [])[:6] or ["Timed mock"],
                "practice": "Full timed mock interview with no notes; score every answer.",
                "resources": []}
    return {"day": day_no, "title": "Final Revision", "skill": "",
            "hours": hours, "topics": (topic_pool or [])[:6] or ["Revise weak topics"],
            "practice": "45-minute mock + revise weak topics only; rest the night before.",
            "resources": []}


def time_allocation(hours_per_day: int) -> list[dict]:
    total = max(1, min(12, hours_per_day or 3)) * 60

    def fmt(mins: int) -> str:
        mins = max(15, mins)
        return f"{mins // 60}h {mins % 60:02d}m" if mins >= 60 else f"{mins}m"

    learn = round(total * 0.35)
    notes = round(total * 0.15)
    practical = round(total * 0.35)
    aloud = max(15, total - learn - notes - practical)
    return [{"activity": "Learn concepts", "time": fmt(learn)},
            {"activity": "Make notes and revise", "time": fmt(notes)},
            {"activity": "Practical exercises", "time": fmt(practical)},
            {"activity": "Interview questions aloud", "time": fmt(aloud)}]


def _group_weeks(days: list[dict], hours: int, gaps: dict) -> list[dict]:
    """Pack global days into 7-day weeks, keeping the frozen week shape."""
    weeks: list[dict] = []
    for start in range(0, len(days), 7):
        chunk = days[start:start + 7]
        no = start // 7 + 1
        foci = [d["title"] for d in chunk if d["skill"]]
        resources: list[dict] = []
        seen: set[str] = set()
        for d in chunk:
            for r in d.get("resources", []):
                if r["url"] not in seen:
                    seen.add(r["url"])
                    resources.append(r)
        if not resources:
            for d in chunk:
                if d["skill"]:
                    resources, _ = _week_resources(d["skill"])
                    if resources:
                        break
        missing = [m["skill"] for m in (gaps or {}).get("missing", [])]
        project_skill = next((d["skill"] for d in chunk if d["skill"]), "")
        weeks.append({
            "week": no,
            "focus": f"Week {no} — {', '.join(foci[:3])}" + (" + mock" if any(
                not d["skill"] for d in chunk) else ""),
            "hours": sum(d.get("hours", hours) for d in chunk),
            "tasks": [f"Day {d['day']} — {d['title']}" for d in chunk],
            "resources": resources[:6],
            "project": (f"Mini-project evidencing {project_skill or (missing[0] if missing else 'your stack')}: "
                        "README with what/why, clean commented code, one measurable outcome, demo GIF/video"),
            "checkpoint": ("Explain each day's topic for 5 minutes with no notes + "
                           "demo the mini-project"),
            "days": chunk,
        })
    return weeks


def fallback_roadmap(gaps: dict, hours_per_day: int = 3) -> dict:
    hours = max(1, min(12, hours_per_day or 3))
    missing = (gaps or {}).get("missing", [])
    if not missing:
        return {"weeks": [], "time_allocation": time_allocation(hours), "total_days": 0}
    alloc = allocate_days(missing, hours)
    days: list[dict] = []
    day_no = 1
    for entry in alloc:
        pool = _topic_bank(entry["skill"])
        per_day = max(1, (len(pool) + entry["days"] - 1) // entry["days"]) if pool else 4
        for i in range(entry["days"]):
            days.append(fallback_day(entry["skill"], "skill", day_no, hours, i,
                                     pool[i * per_day:(i + 1) * per_day]))
            day_no += 1
    skill_names = [a["skill"] for a in alloc]
    rev_topics = []
    for s in skill_names:
        rev_topics.append(f"Revisit {s}: key definitions + trade-offs")
        for pair in kb.get_rag_questions([s], per_skill=2):
            rev_topics.append(f"Self-quiz aloud: {pair['q'][:120]}")
    rev_day = fallback_day(", ".join(skill_names), "revision", day_no, hours,
                           topic_pool=rev_topics[:6])
    rev_day["resources"] = _merged_skill_resources(skill_names)
    days.append(rev_day)
    day_no += 1
    days.append(fallback_day("", "mock", day_no, hours, topic_pool=[
        f"{30 if len(skill_names) > 3 else 45} minutes: {', '.join(skill_names[:3])}",
        f"{30 if len(skill_names) > 3 else 45} minutes: {', '.join(skill_names[3:]) or 'deep-dive Q&A'}",
        "60 minutes: coding practice",
        "Remaining time: revise weak topics, answers without notes"])
    )
    day_no += 1
    days.append(fallback_day("", "final", day_no, hours, topic_pool=[
        "Revise key definitions and comparisons",
        "Review frequently asked interview questions",
        "Draw one system architecture from memory",
        "Practice intro + project explanations"])
    )
    days = days[:MAX_DAYS]
    return {"weeks": _group_weeks(days, hours, gaps),
            "time_allocation": time_allocation(hours), "total_days": len(days)}


def _sanitize_weeks(weeks: list[dict], allowed: dict, gaps: dict,
                    hours_per_day: int = 3) -> list[dict]:
    """Legacy entry: sanitize week-level plans (tasks/resources/project).

    Day-aware plans go through _sanitize_plan; both keep the frozen shape.
    """
    allow = _allow_normalize(allowed)
    missing = [m["skill"] for m in (gaps or {}).get("missing", [])]
    clean: list[dict] = []
    for i, week in enumerate(weeks[:MAX_WEEKS]):
        skill = missing[i] if i < len(missing) else ""
        kept = [{"title": r.get("title", skill), "url": r["url"],
                 "type": allow.get(skill, {}).get(r["url"], "docs")}
                for r in (week.get("resources") or [])
                if isinstance(r, dict) and r.get("url") in allow.get(skill, {})][:4]
        if not kept and skill:
            kept, _ = _week_resources(skill)
        clean.append({
            "week": week.get("week", i + 1),
            "focus": str(week.get("focus", skill or "Upskilling"))[:200],
            "hours": week.get("hours", hours_per_day * 5),
            "tasks": [str(t)[:250] for t in (week.get("tasks") or [])][:6] or [
                f"Learn {skill} fundamentals",
                f"Build a mini-project evidencing {skill}",
                "Write it up + add a resume bullet with a metric"],
            "resources": kept,
            "project": str(week.get("project", f"Mini-project evidencing {skill}"))[:300],
            "checkpoint": str(week.get("checkpoint",
                                       f"Explain {skill} for 5 minutes + demo"))[:300],
        })
    return clean


def _sanitize_plan(weeks: list[dict], allowed: dict, gaps: dict,
                   hours_per_day: int, alloc: list[dict]) -> list[dict]:
    """Validate LLM day-wise plans: fix/renumber days, fill invalid ones
    deterministically, keep resources allowlisted."""
    allow = _allow_normalize(allowed)
    quota = {a["skill"]: a["days"] for a in alloc}
    used = {s: 0 for s in quota}
    closing_kept = 0
    all_days: list[dict] = []
    for week in weeks[:MAX_WEEKS]:
        for raw in (week.get("days") or [])[:7]:
            if len(all_days) >= MAX_DAYS:
                break
            skill = str(raw.get("skill", "") or "")
            if skill and (skill not in quota or used[skill] >= quota[skill]):
                continue  # off-budget or over-budget day — drop, backfill below
            if not skill:
                if closing_kept >= 3:
                    continue
                closing_kept += 1
            topics = [str(t)[:250] for t in (raw.get("topics") or []) if str(t).strip()][:6]
            practice = str(raw.get("practice", "") or "").strip()[:300]
            if not topics or not practice:
                fixed = fallback_day(skill, "skill" if skill else "revision",
                                     len(all_days) + 1, hours_per_day)
                if topics:
                    fixed["topics"] = topics
                if practice:
                    fixed["practice"] = practice
                fixed["title"] = str(raw.get("title", "") or fixed["title"])[:120]
                all_days.append(fixed)
            else:
                all_days.append({
                    "day": len(all_days) + 1,
                    "title": str(raw.get("title", "") or skill or "Study day")[:120],
                    "skill": skill,
                    "hours": raw.get("hours", hours_per_day),
                    "topics": topics,
                    "practice": practice,
                    "resources": [],
                })
            if skill:
                used[skill] += 1
    # Backfill under-covered budgeted skills deterministically.
    for a in alloc:
        while used.get(a["skill"], 0) < a["days"] and len(all_days) < MAX_DAYS:
            all_days.append(fallback_day(a["skill"], "skill", len(all_days) + 1,
                                         hours_per_day))
            used[a["skill"]] += 1
    # Guarantee revision/mock/final closers exist.
    titles = " ".join(d.get("title", "") for d in all_days).lower()
    _rev_topics = []
    for _s in [a["skill"] for a in alloc]:
        _rev_topics.append(f"Revisit {_s}: key definitions + trade-offs")
        for _pair in kb.get_rag_questions([_s], per_skill=1):
            _rev_topics.append(f"Self-quiz aloud: {_pair['q'][:120]}")
    for kind, title, practice in (("revision", "Revision", "Revise all topics, no notes"),
                                  ("mock", "Technical Mock Interview", "Timed mock, no notes"),
                                  ("final", "Final Revision", "Weak topics only")):
        if kind not in titles and len(all_days) < MAX_DAYS:
            _extra = _rev_topics[:4] if kind == "revision" else [practice]
            all_days.append(fallback_day("", kind, len(all_days) + 1,
                                         hours_per_day, topic_pool=_extra))
    # Attach allowlisted resources per day skill.
    for day in all_days:
        if day["skill"]:
            day["resources"], _ = _week_resources(day["skill"])
    all_days = all_days[:MAX_DAYS]
    _merged_res = _merged_skill_resources([a["skill"] for a in alloc])
    for n, day in enumerate(all_days, start=1):
        day["day"] = n
        day["title"] = re.sub(r"\(\s*\)", "", day.get("title", "")).strip() or "Study day"
        if not day.get("skill") and not day.get("resources"):
            day["resources"] = _merged_res
    # Re-group into weeks, preserving any valid LLM week summaries.
    weeks_out = _group_weeks(all_days, hours_per_day, gaps)
    for w_out, w_in in zip(weeks_out, weeks):
        if isinstance(w_in, dict):
            if str(w_in.get("focus", "")).strip():
                w_out["focus"] = str(w_in["focus"])[:200]
            if str(w_in.get("project", "")).strip():
                w_out["project"] = str(w_in["project"])[:300]
            if str(w_in.get("checkpoint", "")).strip():
                w_out["checkpoint"] = str(w_in["checkpoint"])[:300]
    return weeks_out


def build_roadmap(gaps: dict, hours_per_day: int = 3,
                  known: list[str] | None = None) -> tuple[dict, list[dict]]:
    errors: list[dict] = []
    hours = max(1, min(12, hours_per_day or 3))
    missing = (gaps or {}).get("missing", [])
    if not missing:
        return {"weeks": [], "time_allocation": time_allocation(hours),
                "total_days": 0}, errors
    alloc = allocate_days(missing, hours)
    scope = "; ".join(f"{a['skill']}: {a['days']} day(s)" for a in alloc)
    known_str = ", ".join((known or [])[:12]) or "basics"
    names = [a["skill"] for a in alloc]
    allowed = {skill: _week_resources(skill)[1] for skill in names}
    try:
        llm = get_llm("plan")
        if not llm.available:
            raise LLMError("No LLM key — deterministic roadmap.")
        prompt = (
            "You are a senior technical mentor. Create a DAY-WISE interview "
            "preparation roadmap as JSON only — keep it COMPACT (short strings): "
            '{"weeks": [{"week": 1, "focus": str, '
            '"days": [{"day": 1, "title": str, "skill": str, '
            '"topics": [4-6 short str], "practice": str}]}]}. '
            f"Day budget (do not exceed): {scope}; {hours}h per day. "
            f"The learner ALREADY knows: {known_str} — never reteach these; "
            "build ON them (e.g. React knowledge + Docker gap = 'containerize "
            "your React dashboard'). "
            "Rules: (1) every day names CONCRETE topics/subtopics — no generic "
            "'learn X'; (2) one hands-on Practice line per day; finish with one "
            "revision day, one timed mock-interview day, one final-revision day. "
            "Tasks, resources, and project details are added later — omit them."
        )
        plan, rep_errs = llm_json("plan", prompt)
        errors.extend(rep_errs)
        if isinstance(plan, dict) and isinstance(plan.get("weeks"), list) and plan["weeks"]:
            weeks = _sanitize_plan(plan["weeks"], allowed, gaps, hours, alloc)
            alloc_out = plan.get("time_allocation")
            if not (isinstance(alloc_out, list) and alloc_out):
                alloc_out = time_allocation(hours)
            return {"weeks": weeks, "time_allocation": alloc_out,
                    "total_days": sum(len(w.get("days", [])) for w in weeks)}, errors
        raise LLMError("LLM roadmap bad shape.")
    except Exception as exc:  # noqa: BLE001
        errors.append({"node": "roadmap", "message": f"LLM plan skipped: {exc}"})
    out = fallback_roadmap(gaps, hours)
    return out, errors

"""KB tests: curated counts, deterministic fallback, URL policy (offline)."""
from app.agents.interview.generator import generate_interview
from app.agents.roadmap.agent import _sanitize_weeks, build_roadmap, fallback_roadmap
from app.services import kb_service as kb

GAPS = {"strong": ["React"], "partial": [],
        "missing": [{"skill": "Docker", "criticality": "High",
                     "reason": "r", "weeks_to_learn": 3},
                    {"skill": "AWS", "criticality": "Medium",
                     "reason": "r", "weeks_to_learn": 4}],
        "critical_missing": ["Docker"]}


def test_kb_curated_counts():
    counts = kb.kb_counts()
    assert counts["resources"] >= 50, counts
    assert counts["questions"] >= 50, counts


def test_resources_docs_video_course():
    rows = kb.get_resources(["Docker"])["Docker"]
    types = {r["type"] for r in rows}
    assert {"docs", "video"} <= types
    assert all(r["url"].startswith("https://") for r in rows)
    assert any("youtube.com" in r["url"] for r in rows if r["type"] == "video")


def test_roadmap_weeks_carry_video_links():
    plan = fallback_roadmap(GAPS, 3)
    assert len(plan["weeks"]) >= 1  # small plans pack into one week of days
    skill_days = [d for w in plan["weeks"] for d in w.get("days", []) if d["skill"]]
    assert skill_days
    for day in skill_days:
        types = {r["type"] for r in day["resources"]}
        assert "video" in types, day
        assert all(r["url"].startswith("https://") for r in day["resources"])
        assert len(day["topics"]) >= 1 and day["practice"]
    for week in plan["weeks"]:
        assert len(week["tasks"]) >= 1, "weeks must be detailed, not stubs"
        assert "README" in week["project"]


def test_sanitize_drops_invented_urls():
    allowed = {"Docker": {"https://docs.docker.com/get-started/"}}
    weeks = [{"week": 1, "focus": "Docker", "hours": 15, "tasks": ["a"],
              "resources": [{"title": "Fake", "url": "https://evil.example/x"}],
              "project": "p", "checkpoint": "c"}]
    clean = _sanitize_weeks(weeks, allowed, GAPS, 3)
    urls = [r["url"] for r in clean[0]["resources"]]
    known = {r["url"] for r in kb.RESOURCES}
    assert urls, "substitute links missing"
    assert "https://evil.example/x" not in urls
    assert all(u in allowed["Docker"] or u in known for u in urls)


def test_interview_offline_still_full_depth():
    req = ["Docker", "React", "Python", "SQL", "Git", "AWS"]
    out, errs = generate_interview(req, ["React"], GAPS)
    assert out["technical"] and out["hr"]
    assert len(out["technical"]) == 12 and len(out["hr"]) == 8
    assert any("Docker" in t["q"] or "Docker" in t["why_asked"] for t in out["technical"])
    covered = {s for t in out["technical"] for s in req
               if s.lower() in (t["q"] + t["why_asked"]).lower()}
    assert set(req[:4]) <= covered, f"every required skill needs a question: {covered}"
    assert {t["difficulty"] for t in out["technical"]} & {"Easy", "Medium"}
    assert "sources" in out
    for item in out["technical"] + out["hr"]:
        for key in ("q", "difficulty", "why_asked", "ideal_answer", "key_points", "follow_up"):
            assert key in item, key
        assert item["difficulty"] in {"Easy", "Medium", "Hard"}
        assert len(item["key_points"]) >= 1


def test_build_roadmap_offline_shape():
    plan, errors = build_roadmap(GAPS, 3)
    assert plan["weeks"] and errors  # LLM disabled -> fallback + note
    assert all("resources" in w and w["resources"] for w in plan["weeks"])

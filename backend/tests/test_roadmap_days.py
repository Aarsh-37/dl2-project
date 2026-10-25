"""Day-wise roadmap tests: allocation math, day shape, grouping (offline)."""
from app.agents.roadmap.agent import (
    MAX_DAYS,
    allocate_days,
    build_roadmap,
    fallback_day,
    fallback_roadmap,
    time_allocation,
)

GAPS = {"strong": ["React"], "partial": [],
        "missing": [{"skill": "Docker", "criticality": "High",
                     "reason": "r", "weeks_to_learn": 3},
                    {"skill": "AWS", "criticality": "Medium",
                     "reason": "r", "weeks_to_learn": 4}],
        "critical_missing": ["Docker"]}


def test_allocate_scales_with_hours_and_caps():
    low = allocate_days(GAPS["missing"], 2)
    high = allocate_days(GAPS["missing"], 10)
    assert sum(a["days"] for a in high) >= sum(a["days"] for a in low)
    assert all(1 <= a["days"] <= 4 for a in high)
    big = [{"skill": f"S{i}", "criticality": "High", "reason": "r", "weeks_to_learn": 6}
           for i in range(10)]
    assert sum(a["days"] for a in allocate_days(big, 8)) <= 24


def test_fallback_days_have_topics_practice_resources():
    plan = fallback_roadmap(GAPS, 4)
    days = [d for w in plan["weeks"] for d in w.get("days", [])]
    assert 2 <= len(days) <= MAX_DAYS
    assert [d["day"] for d in days] == list(range(1, len(days) + 1))
    for day in days:
        assert len(day["topics"]) >= 1 and day["practice"]
        assert day["hours"] == 4
    titles = [d["title"] for d in days]
    assert any("Mock" in t for t in titles) and any("Revision" in t for t in titles)
    skill_days = [d for d in days if d["skill"]]
    assert all(any(r["type"] == "video" for r in d["resources"]) for d in skill_days)


def test_weeks_group_seven_and_keep_shape():
    plan = fallback_roadmap(GAPS, 4)
    assert all(len(w.get("days", [])) <= 7 for w in plan["weeks"])
    assert plan["total_days"] == sum(len(w.get("days", [])) for w in plan["weeks"])
    for w in plan["weeks"]:
        assert set(w) >= {"week", "focus", "hours", "tasks", "resources",
                          "project", "checkpoint", "days"}
        assert w["tasks"]  # flattened day titles keep old UI working


def test_time_allocation_matches_hours():
    alloc = time_allocation(4)
    assert [a["activity"] for a in alloc] == ["Learn concepts", "Make notes and revise",
                                             "Practical exercises", "Interview questions aloud"]
    assert all(a["time"] for a in alloc)


def test_empty_gaps_empty_plan():
    plan = fallback_roadmap({"missing": []}, 4)
    assert plan["weeks"] == [] and plan["total_days"] == 0
    assert plan["time_allocation"]


def test_build_roadmap_offline_has_new_keys():
    plan, errs = build_roadmap(GAPS, 4, known=["React"])
    assert plan["total_days"] > 0 and plan["time_allocation"] and errs
    assert all(d.get("topics") and d.get("practice")
               for w in plan["weeks"] for d in w.get("days", []))


def test_fallback_day_kinds():
    rev = fallback_day("", "revision", 9, 4, topic_pool=["Revisit Docker"])
    mock = fallback_day("", "mock", 10, 4, topic_pool=["Timed mock"])
    final = fallback_day("", "final", 11, 4)
    assert "Revision" in rev["title"] and "Mock" in mock["title"]
    assert "Final" in final["title"]

"""Graph resilience: checkpointer opt-in + invoke-failure fallback (offline)."""
import app.workflows.career_graph as cg


_STATE = {"user_id": "local", "hours_per_day": 3,
          "resume_text": "Dev with React and Node. Projects: shop app.",
          "job_description": "Hiring Frontend Developer. Required: React, CSS. "
                             "Must have 1 year experience shipping features."}


def test_jobs_node_skipped_by_default(monkeypatch):
    monkeypatch.delenv("CAREERPILOT_JOBS", raising=False)
    assert cg._jobs_enabled() is False
    assert "node_match" not in cg._wave()
    out = cg.run_graph(dict(_STATE))
    assert out["jobs"] == [] and out["job_matches"] == []
    assert not any((t or {}).get("node") in ("match", "discovery", "matching")
                   for t in out.get("agent_trace", []))


def test_jobs_node_runs_when_enabled(monkeypatch):
    monkeypatch.setenv("CAREERPILOT_JOBS", "1")
    assert cg._jobs_enabled() is True
    assert "node_match" in cg._wave()
    out = cg.run_sync(dict(_STATE))
    assert "jobs" in out and "job_matches" in out


def test_checkpointer_off_by_default(monkeypatch):
    monkeypatch.delenv("CAREERPILOT_CHECKPOINT", raising=False)
    cg._saver_cm, cg._saver, cg._saver_failed_at = None, None, 0.0
    assert cg.get_checkpointer() is None


def test_run_graph_falls_back_on_invoke_failure(monkeypatch):
    class Boom:
        def invoke(self, *a, **k):
            raise RuntimeError("pooler died mid-write")

    monkeypatch.setattr(cg, "build_graph", lambda: Boom())
    out = cg.run_graph({"user_id": "local", "hours_per_day": 3,
                        "resume_text": "Asha, QA with Python and SQL. Projects: api tests.",
                        "job_description": "Hiring QA Engineer. Required: Python, SQL, Selenium. "
                                           "Must have 2 years experience testing APIs."})
    assert len(out["interview_questions"]["technical"]) == 12
    assert len(out["interview_questions"]["hr"]) == 8
    assert any(e.get("node") == "graph" for e in out["errors"])
    assert out["ats_result"] and out["skill_gap"] and out["roadmap"]


def test_run_graph_shape_matches_sync():
    state = {"user_id": "local", "hours_per_day": 3,
             "resume_text": "Dev with React and Node. Projects: shop app.",
             "job_description": "Hiring Frontend Developer. Required: React, CSS. "
                                "Must have 1 year experience shipping features."}
    cg._compiled = None  # force fresh compile without checkpointer
    out = cg.run_graph(state)
    for key in ("ats_result", "skill_gap", "roadmap", "interview_questions",
                "optimized_resume", "validation_result", "jobs", "job_matches",
                "career_recommendations", "status", "errors", "agent_trace"):
        assert key in out, key

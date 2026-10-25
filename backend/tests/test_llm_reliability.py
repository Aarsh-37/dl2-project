"""Reliability tests: timeouts, JSON repair, split interview, retry feedback.

All offline — stub LLMs via monkeypatch, never the network.
"""
import app.agents.interview.generator as gen
import app.agents.resume_optimizer.agent as opt
import app.core.llm as core
from app.agents.roadmap.agent import build_roadmap
from app.workflows.career_graph import _validation_feedback

GAPS = {"strong": ["React"], "partial": [],
        "missing": [{"skill": "Docker", "criticality": "High",
                     "reason": "r", "weeks_to_learn": 3}],
        "critical_missing": ["Docker"]}


class _StubLLM:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.available = True
        self.calls = 0

    def invoke(self, prompt):
        self.calls += 1
        out = self.outputs[min(self.calls - 1, len(self.outputs) - 1)]
        if isinstance(out, Exception):
            raise out
        return out


def test_task_timeouts_fit_cpu_ollama():
    assert core.TASK_TIMEOUTS["interview"] >= 240
    assert core.TASK_TIMEOUTS["plan"] >= 120
    llm = core.get_llm("interview")
    assert llm.timeout >= 240
    assert core.get_llm("explain").timeout <= 120


def test_llm_json_repairs_fenced_output(monkeypatch):
    stub = _StubLLM(['```json\n{"a": 1}\n```'])
    monkeypatch.setattr(core, "get_llm", lambda task: stub)
    data, errs = core.llm_json("explain", '{"a": 1}')
    assert data == {"a": 1}


def test_llm_json_repair_retry(monkeypatch):
    stub = _StubLLM(["not json at all", '{"ok": true}'])
    monkeypatch.setattr(core, "get_llm", lambda task: stub)
    data, errs = core.llm_json("explain", "prompt")
    assert data == {"ok": True} and stub.calls == 2 and errs


def test_llm_json_disabled_raises(monkeypatch):
    stub = _StubLLM(['{"a": 1}'])
    stub.available = False
    monkeypatch.setattr(core, "get_llm", lambda task: stub)
    try:
        core.llm_json("explain", "prompt")
        raise AssertionError("should raise")
    except core.LLMError:
        pass


def test_split_interview_merges_tech_and_hr(monkeypatch):
    tech = {"technical": [{"category": "skill", "skill": "Docker", "q": "Q1",
                           "difficulty": "Easy", "why_asked": "Docker gap",
                           "ideal_answer": "A" * 100, "key_points": ["a", "b"],
                           "follow_up": "F?"}]}
    hr = {"hr": [{"category": "behavioral", "q": "H1", "difficulty": "Easy",
                  "why_asked": "w", "ideal_answer": "B" * 100,
                  "key_points": ["c"], "follow_up": "F?"}]}

    def fake_json(task, prompt):
        if "TECHNICAL" in prompt or "senior hiring manager" in prompt:
            return tech, []
        return hr, []

    monkeypatch.setattr(gen, "llm_json", fake_json)
    monkeypatch.setattr(gen, "get_llm", lambda task: _StubLLM([]))
    out, errs = gen.generate_interview(["Docker"], [], GAPS, resume_text="Built x with Docker.")
    assert any("Docker" in t["q"] for t in out["technical"])
    assert out["hr"] and len(out["technical"]) == 12  # sanitizer pads


def test_split_interview_one_side_fails(monkeypatch):
    def fake_json(task, prompt):
        raise core.LLMError("tech boom")

    monkeypatch.setattr(gen, "llm_json", fake_json)
    monkeypatch.setattr(gen, "get_llm", lambda task: _StubLLM([]))
    # Unknown skill: no RAG pairs, no bank rows -> targeted LLM fires -> fails.
    out, errs = gen.generate_interview(["UnobtainiumXYZ"], [], GAPS)
    assert out["technical"] and errs  # templates cover, error noted


def test_optimizer_retry_feedback_reaches_prompt(monkeypatch):
    seen: list[str] = []

    class _Opt:
        available = True

        def invoke(self, prompt):
            seen.append(prompt)
            return "Summary line one. Line two here. Line three done."

    monkeypatch.setattr(opt, "get_llm", lambda task: _Opt())
    out, _ = opt.optimize_resume("resume text", {"required_skills": ["Docker"]},
                                 GAPS, feedback="Previous draft REJECTED: [skills] bad")
    assert out and "Summary" in out["summary"]
    assert "REJECTED" in seen[0]


def test_validation_feedback_formats_new_shape():
    msg = _validation_feedback({"status": "REJECT",
                                "issues": [{"type": "skills", "detail": "bad tok"}]})
    assert "[skills] bad tok" in msg
    assert _validation_feedback({"status": "PASS", "issues": []}) == ""


def test_roadmap_accepts_known_skills():
    plan, errs = build_roadmap(GAPS, 3, known=["React", "JavaScript"])
    assert plan["weeks"] and errs  # offline -> fallback + note

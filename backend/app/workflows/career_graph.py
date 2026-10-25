"""LangGraph orchestrator: prepare (deterministic) -> ONE parallel LLM wave
-> validate (+bounded retry) -> coach. Wall time ~= slowest single LLM call,
not the sum of stages.

Wave (all independent, run concurrently): explainer ∥ roadmap ∥ interview
∥ optimizer ∥ job-match. Coach stays last (needs roadmap + validation +
matches). Every node returns only its OWN new errors (reducer-safe and
run_sync-safe). Uses langgraph when installed, else run_sync() with a
thread-pool wave (same shape).
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from app.agents.ats.explainer import ats_explainer
from app.agents.career_coach.agent import coach_recommendations
from app.agents.interview.generator import generate_interview
from app.agents.jd.agent import analyze_jd
from app.agents.jobs.discovery import discover_jobs
from app.agents.jobs.matching import explain_matches, match_jobs
from app.agents.profile.normalizer import normalize_profile
from app.agents.resume.agent import analyze_resume
from app.agents.resume_optimizer.agent import optimize_resume
from app.agents.resume_optimizer.validator import validate_resume
from app.agents.roadmap.agent import build_roadmap
from app.agents.skill_gap.agent import analyze_gaps
from app.core.config import SKILL_TAXONOMY_CSV
from app.services.ats_service import ats_engine, semantic_score
from app.tools import skill_extract
from app.utils.text_clean import section_text
from app.workflows.routing import MAX_OPTIMIZER_RETRIES, validation_status, validator_route
from app.workflows.state import CareerState

_taxonomy = None


def _taxonomy_cached() -> dict:
    global _taxonomy
    if _taxonomy is None:
        _taxonomy = skill_extract.load_taxonomy(SKILL_TAXONOMY_CSV)
    return _taxonomy


def _new_errors(errs: list[dict], state: CareerState) -> list[dict]:
    """Errors appended during this node only (dedupes against prior state)."""
    seen = state.get("errors", [])
    return [e for e in errs if e not in seen]


def node_prepare(state: CareerState) -> CareerState:
    """Deterministic prep: parse -> profiles -> ATS engine + gaps. No LLM
    except the two fast profile assists (jd/domain + soft skills)."""
    tax = _taxonomy_cached()
    resume_text = (state.get("resume_text", "") or "").strip()
    jd_text = (state.get("job_description", "") or "").strip()
    resume_prof, _ = analyze_resume(resume_text, tax)
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_jd = pool.submit(analyze_jd, jd_text, tax)
        f_cand = pool.submit(normalize_profile, resume_text, tax)
        jd_prof, e1 = f_jd.result()
        cand_prof, e2 = f_cand.result()
    required = jd_prof.get("required_skills", []) or skill_extract.extract_skills(jd_text, tax)
    preferred = jd_prof.get("preferred_skills", [])
    candidate = cand_prof.get("technical", []) or \
        skill_extract.extract_skills(resume_text, tax)
    projects_text = section_text(resume_text, "Projects")
    projects = [skill_extract.extract_skills(l, tax) for l in projects_text.split("\n") if l.strip()]
    gaps, _ = analyze_gaps(candidate, required, preferred, tax)
    try:  # VAE latent suggestions — optional enrichment, never alters gaps
        from app.services.skill_vae import enrich_gaps

        gaps = enrich_gaps(gaps, candidate)
    except Exception:
        gaps.setdefault("suggested", [])
    sem = None
    if os.getenv("CAREERPILOT_SEMANTIC") == "1":
        try:
            sem = semantic_score(resume_text, jd_text)
        except Exception:
            sem = None
    ats = ats_engine({"text": resume_text, "skills": candidate, "projects": projects},
                     {"text": jd_text, "required": required, "preferred": preferred}, semantic=sem)
    return {"resume_text": resume_text, "job_description": jd_text,
            "resume_profile": resume_prof, "jd_profile": jd_prof,
            "candidate_profile": {**cand_prof, "technical": candidate},
            "ats_result": ats, "skill_gap": gaps,
            "_required": required, "_preferred": preferred, "_candidate": candidate,
            "errors": e1 + e2}


def node_explain(state: CareerState) -> CareerState:
    """LLM explains the engine score (never re-scores)."""
    errs: list[dict] = list(state.get("errors", []))
    ats = ats_explainer(state.get("resume_text", ""), state.get("job_description", ""),
                        state.get("ats_result", {}), errs)
    return {"ats_result": ats, "errors": _new_errors(errs, state)}


def node_roadmap(state: CareerState) -> CareerState:
    """LLM roadmap from gaps (KB URLs only, sanitized)."""
    roadmap, errs = build_roadmap(state.get("skill_gap", {}),
                                  state.get("hours_per_day", 3),
                                  state.get("candidate_profile", {}).get("technical", []))
    return {"roadmap": roadmap, "errors": errs}


def node_interview(state: CareerState) -> CareerState:
    """RAG-first interview prep (LLM only fills retrieval gaps)."""
    jd_prof = state.get("jd_profile", {})
    interview, errs = generate_interview(
        jd_prof.get("required_skills", []),
        state.get("candidate_profile", {}).get("technical", []),
        state.get("skill_gap", {}), jd_prof.get("role", ""),
        state.get("resume_text", ""))
    return {"interview_questions": interview, "errors": errs}


def node_optimize(state: CareerState) -> CareerState:
    """Constrained LLM resume rewrite (facts only, validator-checked later)."""
    optimized, errs = optimize_resume(state.get("resume_text", ""),
                                      state.get("jd_profile", {}),
                                      state.get("skill_gap", {}))
    return {"optimized_resume": optimized, "errors": errs}


def node_match(state: CareerState) -> CareerState:
    """Job discovery + deterministic matching (+LLM explain of top picks)."""
    jobs, errs = discover_jobs(state.get("candidate_profile", {}))
    matches = match_jobs(jobs, state.get("candidate_profile", {}))
    matches = explain_matches(matches, errs)
    return {"jobs": jobs, "job_matches": matches,
            "errors": [e for e in errs if e not in state.get("errors", [])]}


def _validation_feedback(validation: dict) -> str:
    issues = validation.get("issues", []) or []
    if not issues:
        return ""
    return "Previous draft was REJECTED for: " + "; ".join(
        f"[{i.get('type')}] {i.get('detail')}" for i in issues if isinstance(i, dict))[:800]


def node_validate(state: CareerState) -> CareerState:
    """Deterministic gate + ONE bounded LLM retry with validator feedback."""
    retries = int((state.get("validation_result", {}) or {}).get("retries", 0))
    optimized = state.get("optimized_resume")
    errs: list[dict] = []
    validation = validate_resume(state.get("resume_text", ""), optimized)
    while validator_route(validation, retries) == "retry":
        retries += 1
        feedback = _validation_feedback(validation)
        retry_draft, e2 = optimize_resume(state.get("resume_text", ""),
                                          state.get("jd_profile", {}),
                                          state.get("skill_gap", {}), feedback)
        errs = errs + e2
        if retry_draft is not None:
            optimized = retry_draft
        validation = validate_resume(state.get("resume_text", ""), optimized)
    out: CareerState = {"optimized_resume": optimized,
                        "validation_result": {**validation, "retries": retries},
                        "errors": errs}
    if retries >= MAX_OPTIMIZER_RETRIES and validation_status(validation) != "PASS":
        out["errors"] = errs + [{"node": "validator",
                                 "message": " retries exhausted — needs human approval."}]
    return out


def node_coach(state: CareerState) -> CareerState:
    """Final synthesis + done/partial status (contracts.md §5.1)."""
    recs, errs = coach_recommendations(state.get("ats_result", {}),
                                       state.get("skill_gap", {}),
                                       state.get("job_matches", []),
                                       state.get("roadmap", {}),
                                       state.get("validation_result", {}))
    has_real_jobs = any((j or {}).get("source") != "link"
                        for j in (state.get("job_matches", []) or []))
    jobs_ok = (not _jobs_enabled()) or has_real_jobs
    status = ("done" if (state.get("optimized_resume") and jobs_ok) else "partial")
    out: CareerState = {"career_recommendations": recs, "status": status, "errors": errs}
    if not _jobs_enabled():  # keep the result shape stable without the jobs node
        out["jobs"] = []
        out["job_matches"] = []
    return out


_WAVE = ("node_explain", "node_roadmap", "node_interview", "node_optimize", "node_match")
_NODES = {"node_explain": node_explain, "node_roadmap": node_roadmap,
          "node_interview": node_interview, "node_optimize": node_optimize,
          "node_match": node_match}


def _jobs_enabled() -> bool:
    """Job discovery + matching is OFF by default: external API unreliable and
    we don't want LLM effort spent there. Set CAREERPILOT_JOBS=1 to re-enable."""
    return os.getenv("CAREERPILOT_JOBS", "0") == "1"


def _wave() -> tuple[str, ...]:
    return _WAVE if _jobs_enabled() else tuple(n for n in _WAVE if n != "node_match")


def run_sync(state: CareerState) -> CareerState:
    """Same shape as the graph: prepare, then ONE thread-pool wave, then
    validate + coach. Sequential fallback when langgraph is missing."""
    from app.core.llm import clear_call_log, drain_call_log

    clear_call_log()
    merged: dict = dict(state)
    merged.setdefault("errors", [])

    def apply(patch: dict):
        errs = patch.pop("errors", [])
        merged.update(patch)
        merged["errors"] = list(merged.get("errors", [])) + list(errs or [])

    apply(node_prepare(merged))
    wave = _wave()
    with ThreadPoolExecutor(max_workers=len(wave)) as pool:
        futures = {pool.submit(_NODES[name], dict(merged)): name for name in wave}
        waves = [(futures[f], f.result()) for f in futures]
    for name in wave:  # deterministic merge order
        apply(dict(next(p for n, p in waves if n == name)))
    apply(node_validate(merged))
    apply(node_coach(merged))
    merged["agent_trace"] = drain_call_log()
    return merged


_saver_cm = None
_saver = None
_saver_failed_at = 0.0
_compiled = None

import time as _time

_CHECKPOINTER_RETRY_S = 300  # don't pay connect timeout on every request when DB is down


def get_checkpointer():
    """Postgres checkpointer on DATABASE_URL_DIRECT (never the pooler).

    Opt-in via CAREERPILOT_CHECKPOINT=1 (default OFF): nothing currently
    reads checkpoints back (thread_id is random per run; HITL approval is a
    separate endpoint), and a flaky checkpointer used to fail entire runs.
    Cached for process lifetime; failures remembered briefly.
    """
    global _saver_cm, _saver, _saver_failed_at
    if os.getenv("CAREERPILOT_CHECKPOINT", "0") != "1":
        return None
    if _saver is not None:
        return _saver
    if _time.monotonic() - _saver_failed_at < _CHECKPOINTER_RETRY_S:
        return None
    try:
        try:  # v3.x path
            from langgraph.checkpoint.postgres import PostgresSaver
        except ImportError:  # pre-3.x path
            from langgraph_checkpoint_postgres import PostgresSaver

        url = (os.getenv("DATABASE_URL_DIRECT") or os.getenv("DATABASE_URL_POOLER") or "")
        url = url.replace("postgresql+psycopg://", "postgresql://").replace(
            "postgresql+asyncpg://", "postgresql://")
        if not url:
            return None
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}connect_timeout=10"  # fail fast, never hang tests/API
        _saver_cm = PostgresSaver.from_conn_string(url)
        _saver = _saver_cm.__enter__()
        _saver.setup()
        return _saver
    except Exception:
        _saver_cm, _saver = None, None
        _saver_failed_at = _time.monotonic()
        return None


def build_graph():
    """LangGraph StateGraph when langgraph is installed, else sync runner.

    prepare -> [explain ∥ roadmap ∥ interview ∥ optimize ∥ match] ->
    validate -> coach -> END. Compiled once per process.
    """
    global _compiled
    if _compiled is not None:
        return _compiled
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        return None
    g = StateGraph(CareerState)
    g.add_node("prepare", node_prepare)
    g.add_node("explain", node_explain)
    g.add_node("roadmap", node_roadmap)
    g.add_node("interview", node_interview)
    g.add_node("optimize", node_optimize)
    g.add_node("validate", node_validate)
    g.add_node("coach", node_coach)
    branches = ["explain", "roadmap", "interview", "optimize"]
    if _jobs_enabled():
        g.add_node("match", node_match)
        branches.append("match")
    g.add_edge(START, "prepare")
    for branch in branches:
        g.add_edge("prepare", branch)
        g.add_edge(branch, "validate")
    g.add_edge("validate", "coach")
    g.add_edge("coach", END)
    _compiled = g.compile(checkpointer=get_checkpointer())
    return _compiled


def run_graph(state: CareerState, thread_id: str | None = None) -> CareerState:
    """Invoke the LangGraph build (or the sync fallback without langgraph).

    thread_id keys the Postgres checkpoint for resume/retry per run.
    A failing graph NEVER fails the request: any invoke error is noted
    and the identical-shape run_sync result is returned instead.
    """
    from app.core.llm import clear_call_log, drain_call_log

    graph = build_graph()
    if graph is None:
        return run_sync(state)
    import uuid

    clear_call_log()
    try:
        out = graph.invoke(state, config={"configurable": {
            "thread_id": thread_id or f"run-{uuid.uuid4().hex[:12]}"}})
    except Exception as exc:
        partial_trace = drain_call_log()  # keep the failed attempt visible
        out = run_sync(state)
        out.setdefault("errors", []).append(
            {"node": "graph", "message": f"Graph invoke failed, used sync path: {exc}"})
        out["agent_trace"] = partial_trace + out.get("agent_trace", [])
        return out
    out.setdefault("errors", [])
    out.setdefault("status", "partial")
    out["agent_trace"] = drain_call_log()
    return out

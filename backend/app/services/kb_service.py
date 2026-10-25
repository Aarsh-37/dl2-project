"""Knowledge-base service: learning resources + interview question bank.

Single source of truth for KB content: scripts/seed_kb.py upserts these rows
into Supabase; agents read DB first and fall back here. URL policy
(contracts.md §7): only official docs, well-known free courses/practice, and
generated YouTube *search* links (never invented deep video URLs).
CAREERPILOT_KB=0 forces the curated fallback (tests/CI/offline).
"""
from __future__ import annotations

import os
from urllib.parse import quote_plus

YOUTUBE_SEARCH = "https://www.youtube.com/results?search_query="


def _yt(skill: str, suffix: str = "tutorial full course") -> str:
    return YOUTUBE_SEARCH + quote_plus(f"{skill} {suffix}")


def _docs(skill: str, title: str, url: str) -> dict:
    return {"skill": skill, "title": title, "url": url, "type": "docs"}


def _video(skill: str, title: str, query: str | None = None) -> dict:
    return {"skill": skill, "title": title,
            "url": _yt(query) if query else _yt(skill), "type": "video"}


def _course(skill: str, title: str, url: str) -> dict:
    return {"skill": skill, "title": title, "url": url, "type": "course"}


def _practice(skill: str, title: str, url: str) -> dict:
    return {"skill": skill, "title": title, "url": url, "type": "practice"}


RESOURCES: list[dict] = [
    # Python
    _docs("Python", "Python — official tutorial", "https://docs.python.org/3/tutorial/"),
    _video("Python", "Python full course (video)", "Python full course for beginners"),
    _course("Python", "Scientific Computing with Python (freeCodeCamp)",
            "https://www.freecodecamp.org/learn/scientific-computing-with-python/"),
    # JavaScript
    _docs("JavaScript", "JavaScript — MDN", "https://developer.mozilla.org/en-US/docs/Web/JavaScript"),
    _video("JavaScript", "JavaScript full course (video)", "JavaScript full course for beginners"),
    _course("JavaScript", "JS Algorithms & Data Structures (freeCodeCamp)",
            "https://www.freecodecamp.org/learn/javascript-algorithms-and-data-structures/"),
    # TypeScript
    _docs("TypeScript", "TypeScript — official docs", "https://www.typescriptlang.org/docs/"),
    _video("TypeScript", "TypeScript full course (video)"),
    _practice("TypeScript", "TypeScript track (Exercism)", "https://exercism.org/tracks/typescript"),
    # React
    _docs("React", "React — official learn", "https://react.dev/learn"),
    _video("React", "React full course (video)"),
    _course("React", "Full Stack Open — React/Node (free)", "https://fullstackopen.com/en/"),
    # Node.js
    _docs("Node.js", "Node.js — official docs", "https://nodejs.org/en/docs"),
    _video("Node.js", "Node.js full course (video)"),
    _course("Node.js", "Full Stack Open — backend (free)", "https://fullstackopen.com/en/"),
    # SQL
    _docs("SQL", "PostgreSQL — official docs", "https://www.postgresql.org/docs/"),
    _video("SQL", "SQL full course (video)"),
    _course("SQL", "SQLBolt — interactive SQL lessons", "https://sqlbolt.com/"),
    # PostgreSQL
    _docs("PostgreSQL", "PostgreSQL — official docs", "https://www.postgresql.org/docs/"),
    _video("PostgreSQL", "PostgreSQL full course (video)"),
    _course("PostgreSQL", "PostgreSQL Tutorial", "https://www.postgresqltutorial.com/"),
    # Docker
    _docs("Docker", "Docker — get started", "https://docs.docker.com/get-started/"),
    _video("Docker", "Docker full course (video)"),
    _practice("Docker", "Play with Docker (official lab)", "https://labs.play-with-docker.com/"),
    # Kubernetes
    _docs("Kubernetes", "Kubernetes — official docs", "https://kubernetes.io/docs/home/"),
    _video("Kubernetes", "Kubernetes full course (video)"),
    _course("Kubernetes", "Kubernetes basics tutorial", "https://kubernetes.io/docs/tutorials/kubernetes-basics/"),
    # AWS
    _docs("AWS", "AWS Skill Builder (free tier)", "https://skillbuilder.aws/"),
    _video("AWS", "AWS full course (video)", "AWS certified cloud practitioner full course"),
    _course("AWS", "AWS Training & Certification", "https://aws.amazon.com/training/"),
    # Git
    _docs("Git", "Git — official docs", "https://git-scm.com/doc"),
    _video("Git", "Git full course (video)"),
    _practice("Git", "Learn Git Branching (interactive)", "https://learngitbranching.js.org/"),
    # Java
    _docs("Java", "Java — Oracle docs", "https://docs.oracle.com/en/java/"),
    _video("Java", "Java full course (video)"),
    _course("Java", "Dev.java — learn Java", "https://dev.java/learn/"),
    # Go
    _docs("Go", "Go — official docs", "https://go.dev/doc/"),
    _video("Go", "Golang full course (video)"),
    _practice("Go", "A Tour of Go (interactive)", "https://go.dev/tour/"),
    # Rust
    _docs("Rust", "The Rust Book", "https://doc.rust-lang.org/book/"),
    _video("Rust", "Rust full course (video)"),
    _practice("Rust", "Rust by Example", "https://doc.rust-lang.org/rust-by-example/"),
    # CSS
    _docs("CSS", "CSS — MDN", "https://developer.mozilla.org/en-US/docs/Web/CSS"),
    _video("CSS", "CSS full course (video)"),
    _practice("CSS", "Flexbox Froggy (interactive)", "https://flexboxfroggy.com/"),
    # Machine Learning
    _docs("Machine Learning", "Google ML Crash Course (free)",
          "https://developers.google.com/machine-learning/crash-course"),
    _video("Machine Learning", "Machine learning full course (video)"),
    _course("Machine Learning", "Kaggle Learn — micro-courses", "https://www.kaggle.com/learn"),
    # C++
    _docs("C++", "C++ tutorial (cplusplus.com)", "https://cplusplus.com/doc/tutorial/"),
    _video("C++", "C++ full course (video)"),
    _course("C++", "LearnCpp.com (free tutorial)", "https://www.learncpp.com/"),
    # HTML
    _docs("HTML", "HTML — MDN", "https://developer.mozilla.org/en-US/docs/Web/HTML"),
    _video("HTML", "HTML full course (video)"),
    _course("HTML", "freeCodeCamp Responsive Web Design",
            "https://www.freecodecamp.org/learn/responsive-web-design/"),
]


def _q(skill: str, category: str, difficulty: str, q: str,
       ideal: str, points: list[str]) -> dict:
    return {"skill": skill, "category": category, "difficulty": difficulty,
            "q": q, "ideal_answer": ideal, "key_points": points}


QUESTIONS: list[dict] = [
    _q("Python", "technical", "Easy", "What are Python lists, tuples, and dicts — when do you use each?",
       "Lists are mutable sequences, tuples immutable, dicts key-value maps; choose by mutation + lookup needs.",
       ["Mutability", "Use cases", "Example"]),
    _q("Python", "technical", "Medium", "Explain list comprehensions and generators with an example.",
       "Comprehensions build collections inline; generators yield lazily — use generators for large streams.",
       ["Syntax", "Laziness", "Memory trade-off"]),
    _q("Python", "technical", "Hard", "How does the GIL affect multithreading, and what are the workarounds?",
       "The GIL serializes bytecode so threads don't speed CPU work; use multiprocessing, asyncio for I/O, or C extensions.",
       ["GIL", "I/O vs CPU", "Workarounds"]),
    _q("JavaScript", "technical", "Easy", "Explain var vs let vs const.",
       "var is function-scoped and hoisted; let/const are block-scoped, const forbids reassignment.",
       ["Scope", "Hoisting", "Reassignment"]),
    _q("JavaScript", "technical", "Medium", "What is the event loop and how do promises work?",
       "Single-threaded loop with task/microtask queues; promises resolve via microtasks without blocking.",
       ["Call stack", "Microtasks", "Non-blocking I/O"]),
    _q("TypeScript", "technical", "Medium", "Why use TypeScript over JavaScript? Explain interfaces vs types.",
       "Static types catch bugs early; interfaces describe object shapes and support extension, types are more flexible unions.",
       ["Type safety", "Interfaces", "Migration benefit"]),
    _q("TypeScript", "technical", "Easy", "What does the `unknown` type mean and when is it safer than `any`?",
       "unknown forces narrowing before use, unlike any which disables checking — prefer unknown at boundaries.",
       ["Narrowing", "any risks", "API boundaries"]),
    _q("React", "technical", "Easy", "Explain components, props, and state in React.",
       "Components render UI; props flow down, state is local and triggers re-render on change.",
       ["Props vs state", "Re-render", "Example"]),
    _q("React", "technical", "Medium", "What are hooks? Explain useEffect dependencies and cleanup.",
       "Hooks add state/effects to functions; the dep array controls re-runs, cleanup avoids leaks.",
       ["Rules of hooks", "Deps array", "Cleanup"]),
    _q("React", "technical", "Hard", "How do you optimize a slow React app?",
       "Profile first, then memoize components/callbacks, virtualize long lists, code-split routes, and fix state shape.",
       ["Profiling", "Memoization", "Code splitting"]),
    _q("Node.js", "technical", "Medium", "How does Node.js handle concurrency with a single thread?",
       "Event loop + libuv threadpool for I/O; CPU-bound work blocks — offload or worker threads.",
       ["Event loop", "Blocking vs non-blocking", "Scaling"]),
    _q("Node.js", "technical", "Easy", "What is npm and how do dependencies vs devDependencies differ?",
       "npm manages packages; dependencies ship to production, devDependencies are build/test only.",
       ["package.json", "Lockfile", "Semver"]),
    _q("System Design", "technical", "Medium", "Design a URL shortener for 100M URLs a day.",
       "Hash IDs (base62), stateless API behind a load balancer, KV store with cache, rate limiting, analytics pipeline.",
       ["Capacity math", "ID generation", "Bottlenecks"]),
    _q("System Design", "technical", "Hard", "How do you scale a read-heavy feed from 1k to 1M users?",
       "Cache hot reads, read replicas, fan-out-on-write vs pull, pagination, CDN for media, shard when one DB saturates.",
       ["Caching", "Fan-out", "Sharding"]),
    _q("System Design", "technical", "Easy", "Monolith vs microservices: how do you choose?",
       "Start modular monolith; split when teams/services need independent deploy and scaling — distribution has real costs.",
       ["Trade-offs", "Team size", "Operational cost"]),
    _q("SQL", "technical", "Easy", "JOIN types: when do you use INNER, LEFT, and FULL JOIN?",
       "INNER keeps matches; LEFT keeps all left rows; FULL keeps both sides with NULLs for misses.",
       ["Row preservation", "NULL handling", "Example"]),
    _q("SQL", "technical", "Medium", "How do indexes speed up queries and what do they cost?",
       "Indexes give O(log n) lookups via B-trees but slow writes and use space — index selective WHERE/JOIN columns.",
       ["B-tree", "Write cost", "Selectivity"]),
    _q("SQL", "technical", "Hard", "Explain window functions (ROW_NUMBER, RANK, LAG) with a use case.",
       "Window functions compute across rows without collapsing groups — e.g. ranking top-N per category or period-over-period deltas.",
       ["OVER clause", "Ranking", "Use case"]),
    _q("PostgreSQL", "technical", "Easy", "What makes PostgreSQL different from MySQL?",
       "Advanced types (JSONB, arrays), stronger standards compliance, extensibility, and MVCC concurrency.",
       ["JSONB", "Extensibility", "MVCC"]),
    _q("PostgreSQL", "technical", "Medium", "How do you design schema, indexes, and EXPLAIN a slow query?",
       "Normalize core entities, index join/filter columns, read EXPLAIN ANALYZE for seq scans and fix with indexes or rewrites.",
       ["Schema design", "EXPLAIN", "Index strategy"]),
    _q("Docker", "technical", "Easy", "What is a Docker image vs a container?",
       "Images are immutable templates; containers are runnable instances with isolated filesystems.",
       ["Layers", "Isolation", "Example run"]),
    _q("Docker", "technical", "Medium", "Explain multi-stage builds and why they shrink images.",
       "Build in one stage, copy only artifacts to a slim runtime stage — drops toolchains from production.",
       ["Stages", "Image size", "Security"]),
    _q("Docker", "technical", "Hard", "How do you debug a container that exits immediately?",
       "Override entrypoint to sleep, inspect logs/filesystem, check exit codes, resource limits, and volume mounts.",
       ["Logs", "Entrypoint override", "Exit codes"]),
    _q("Kubernetes", "technical", "Medium", "What are Pods, Deployments, and Services?",
       "Pods run containers; Deployments manage replicas/rollouts; Services give stable networking.",
       ["Abstractions", "Rollouts", "Discovery"]),
    _q("Kubernetes", "technical", "Hard", "How would you debug a CrashLoopBackOff pod?",
       "Check logs/events, probe config, resource limits, image/entrypoint; reproduce with run overrides.",
       ["kubectl logs/describe", "Probes", "Resources"]),
    _q("AWS", "technical", "Easy", "EC2 vs Lambda: when do you pick each?",
       "EC2 for long-running/controllable servers; Lambda for event-driven, spiky, pay-per-use workloads.",
       ["Pricing", "Scaling", "Cold starts"]),
    _q("AWS", "technical", "Medium", "How do S3, IAM, and VPC fit in a secure web deployment?",
       "Static assets on S3, least-privilege IAM roles, app in private VPC subnets behind a load balancer.",
       ["Least privilege", "Network isolation", "Static hosting"]),
    _q("AWS", "technical", "Hard", "How would you design for failure across availability zones?",
       "Multi-AZ data, stateless app tier behind ALB, health checks with auto-replacement, backups with tested restores.",
       ["Multi-AZ", "Statelessness", "Recovery"]),
    _q("Git", "technical", "Easy", "Explain git add, commit, push, pull — and merge vs rebase.",
       "Stage, snapshot, publish, sync; merge preserves history, rebase linearizes — never rebase shared branches.",
       ["Workflow", "History shape", "Team rule"]),
    _q("Git", "technical", "Medium", "How do you resolve a merge conflict safely?",
       "Pull, open conflict markers, choose hunks deliberately, test, commit — communicate on shared branches.",
       ["Markers", "Testing", "Communication"]),
    _q("Java", "technical", "Easy", "OOP pillars in Java with one example each.",
       "Encapsulation, inheritance, polymorphism, abstraction — e.g. an abstract Shape with Circle.area().",
       ["4 pillars", "Example", "When to use"]),
    _q("Java", "technical", "Medium", "How does garbage collection work and what causes memory leaks in Java?",
       "GC reclaims unreachable objects; leaks come from lingering references like static collections or unclosed resources.",
       ["Reachability", "Static refs", "try-with-resources"]),
    _q("Go", "technical", "Medium", "Explain goroutines and channels with an example.",
       "Lightweight concurrent functions multiplexed on threads; channels safely pass data between them.",
       ["Concurrency model", "Buffered vs unbuffered", "Example"]),
    _q("Go", "technical", "Easy", "How does Go handle errors without exceptions?",
       "Explicit multiple return values with error; check and wrap with context at each layer.",
       ["error values", "Wrapping", "No exceptions"]),
    _q("Rust", "technical", "Medium", "Explain ownership, borrowing, and lifetimes.",
       "One owner, moves by default; borrows are checked at compile time so memory is safe without GC.",
       ["Move vs copy", "Borrow rules", "Lifetime elision"]),
    _q("Rust", "technical", "Easy", "Result vs Option: when do you use each?",
       "Option for nullable values, Result for fallible operations — both force explicit handling via match/?",
       ["Nullability", "Errors", "Combinators"]),
    _q("CSS", "technical", "Easy", "Explain the box model and Flexbox vs Grid.",
       "Content/padding/border/margin; Flexbox for 1-D layouts, Grid for 2-D — combine as needed.",
       ["Box parts", "1-D vs 2-D", "Example"]),
    _q("CSS", "technical", "Hard", "How do CSS specificity and cascade actually resolve conflicts?",
       "Inline > IDs > classes/attributes > elements; later rules win ties — keep specificity flat with BEM or layers.",
       ["Specificity weights", "Cascade layers", "Debugging"]),
    _q("CSS", "technical", "Medium", "How do you make a responsive layout without frameworks?",
       "Fluid units, Flexbox/Grid, media queries at content breakpoints, responsive images and meta viewport.",
       ["Breakpoints", "Units", "Testing"]),
    _q("Machine Learning", "technical", "Medium", "How do you detect and fix overfitting?",
       "Gap between train/val metrics; fix with more data, regularization, dropout, early stopping, cross-validation.",
       ["Bias-variance", "Regularization", "Validation"]),
    _q("Machine Learning", "technical", "Easy", "Supervised vs unsupervised learning with examples.",
       "Supervised learns from labels (classification/regression); unsupervised finds structure (clustering).",
       ["Labels", "Examples", "Metrics"]),
    _q("C++", "technical", "Medium", "Explain pointers vs references and smart pointers.",
       "Pointers can be null/reseated, references alias; unique_ptr/shared_ptr manage lifetime automatically.",
       ["Ownership", "RAII", "Leak avoidance"]),
    _q("C++", "technical", "Easy", "What happens during compilation: preprocess, compile, link?",
       "Headers expand, translation units compile to objects, linker resolves symbols into a binary.",
       ["Stages", "Headers", "Link errors"]),
    _q("HTML", "technical", "Easy", "What are semantic HTML tags and why do they matter?",
       "Tags like header/main/article describe meaning — better accessibility, SEO, and maintainability.",
       ["Examples", "Accessibility", "SEO"]),
    _q("HTML", "technical", "Medium", "How do forms, validation, and accessibility work together?",
       "Native inputs with labels, required/pattern validation, ARIA only where native falls short.",
       ["Labels", "Native validation", "ARIA"]),
    _q("General", "hr", "Easy", "Tell me about yourself.",
       "Present role in one line, proof with a metric in two lines, why this role in one line.",
       ["Present", "Proof", "Fit"]),
    _q("General", "hr", "Easy", "Why do you want this role at this company?",
       "Connect their stack/mission to your evidence; name one concrete contribution you'd make first.",
       ["Research", "Evidence", "Contribution"]),
    _q("General", "hr", "Medium", "Describe a disagreement with a teammate and how you resolved it.",
       "Situation, options traded off, data or experiment used, agreed rubric going forward.",
       ["STAR", "Trade-offs", "Outcome"]),
    _q("General", "hr", "Medium", "Tell me about a failure and what you changed afterwards.",
       "Own the mistake, show the fix and the guardrail you added so it can't recur.",
       ["Ownership", "Fix", "Prevention"]),
    _q("General", "hr", "Easy", "What are your strengths and weaknesses?",
       "Strengths backed by evidence; weakness framed as an active improvement with proof of progress.",
       ["Evidence", "Honesty", "Growth"]),
    _q("General", "hr", "Medium", "Where do you see yourself in 2 years?",
       "Deeper craft in this stack plus broader ownership — tied to this team's trajectory.",
       ["Ambition", "Realism", "Team fit"]),
    _q("General", "hr", "Easy", "Do you have questions for us?",
       "Ask about the team's stack, onboarding, success metrics, and engineering culture.",
       ["Curiosity", "Role clarity", "Culture"]),
    _q("General", "hr", "Medium", "Describe a time you learned a technology quickly under deadline.",
       "Name the gap, the plan, the resources, and the shipped result with a metric.",
       ["Gap", "Plan", "Result"]),
]


def _kb_enabled() -> bool:
    return os.getenv("CAREERPILOT_KB", "1") == "1"


# Small in-process TTL cache for KB reads: the seed tables barely change,
# and this turns ~15 Supabase round-trips per analysis into memory lookups
# after the first warm run. Thread-safe; failures are never cached long —
# callers already treat None/[] as "use curated fallback".
import threading as _threading
import time as _time

_CACHE_TTL = 300
_CACHE_MAX = 512
_CACHE: dict = {}
_CACHE_LOCK = _threading.Lock()


def _cache_get(key) -> tuple[bool, object]:
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and hit[0] > _time.monotonic():
            return True, hit[1]
        elif hit:
            del _CACHE[key]
    return False, None


def _cache_set(key, value) -> None:
    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = (_time.monotonic() + _CACHE_TTL, value)


# Hard deadline for any single DB round-trip. Driver timeouts don't cover
# DNS stalls, so a stuck query is quarantined in a daemon worker instead of
# hanging the request thread. Callers already treat None/[] as "fall back".
from concurrent.futures import ThreadPoolExecutor as _Executor

_DB_EXEC = _Executor(max_workers=8, thread_name_prefix="kbdb")
_DB_TIMEOUT = 10  # indexed tiny queries answer in <2s healthy; never wait longer
_MISS = object()

# Circuit breaker: 3 consecutive DB failures -> skip DB for 2 min and serve
# curated fallbacks instantly. Resets on first success. This is what keeps a
# flaky pooler from stacking 25s stalls into minutes of latency.
_CIRCUIT = {"fails": 0, "skip_until": 0.0}


def _circuit_ok() -> bool:
    return _time.monotonic() >= _CIRCUIT["skip_until"]


def _circuit_note(success: bool) -> None:
    with _CACHE_LOCK:
        if success:
            _CIRCUIT["fails"] = 0
            _CIRCUIT["skip_until"] = 0.0
        else:
            _CIRCUIT["fails"] += 1
            if _CIRCUIT["fails"] >= 3:
                _CIRCUIT["skip_until"] = _time.monotonic() + 120


def _guarded(fn, default):
    """Run a DB read with deadline + circuit breaker. Never raises."""
    if not _circuit_ok():
        return default
    out = _bounded(fn, default=_MISS)
    if out is _MISS:
        _circuit_note(False)
        return default
    _circuit_note(True)
    return out


def _bounded(fn, default=None, timeout: int = _DB_TIMEOUT):
    try:
        return _DB_EXEC.submit(fn).result(timeout=timeout)
    except Exception:
        return default


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


def semantic_search(table: str, query: str, limit: int = 3) -> list[dict] | None:
    """pgvector cosine retrieval over embedded rows. None when unavailable.

    This is the vector half of RAG: finds related rows even when the skill
    name doesn't match exactly (e.g. query 'containers' -> Docker rows).
    Requires backfilled embeddings (scripts/backfill_embeddings.py) + ST.
    """
    if not _kb_enabled() or not query.strip():
        return None
    cached, val = _cache_get(("semantic_search", table, query, limit))
    if cached:
        return val  # type: ignore[return-value]
    try:
        from app.tools.embeddings import embed

        vec = embed(query)
        if not vec:
            return None
        from app.db.session import get_session
        from sqlalchemy import text

        cols = {"learning_resources": "skill, title, url, type",
                "question_bank": "skill, category, difficulty, q, ideal_answer, key_points",
                "kb_chunks": "source, skill, category, page, text"}
        if table not in cols:
            return None
        db = get_session()

        def do_search():
            try:
                rows = db.execute(
                    text(f"SELECT {cols[table]} FROM {table} WHERE embedding IS NOT NULL "
                         f"ORDER BY embedding <=> CAST(:emb AS vector) LIMIT :limit"),
                    {"emb": _vec_literal(vec), "limit": limit},
                ).mappings().all()
                return [dict(r) for r in rows] or None
            finally:
                db.close()

        try:
            out = _guarded(do_search, default=None)
            _cache_set(("semantic_search", table, query, limit), out)
            return out
        except Exception:
            return None
    except Exception:
        return None


def semantic_chunks(query: str, limit: int = 3, category: str | None = None,
                    skill: str | None = None) -> list[dict]:
    """Retrieve raw prep-material passages for RAG prompts.

    Returns [{source, skill, category, page, text}] (text truncated for
    prompts). [] when KB is off/unavailable — callers skip RAG context.
    """
    if not _kb_enabled() or not (query or "").strip():
        return []
    cached, val = _cache_get(("semantic_chunks", query, limit, category, skill))
    if cached:
        return val  # type: ignore[return-value]
    try:
        from app.tools.embeddings import embed

        vec = embed(query)
        if not vec:
            return []
        from app.db.session import get_session
        from sqlalchemy import text

        conds: list[str] = ["embedding IS NOT NULL"]
        params: dict = {"limit": limit}
        if category:
            conds.append("category = :cat")
            params["cat"] = category
        if skill:
            conds.append("skill = :skill")
            params["skill"] = skill
        params["emb"] = _vec_literal(vec)
        db = get_session()

        def do_chunks():
            try:
                rows = db.execute(
                    text("SELECT source, skill, category, page, text FROM kb_chunks "
                         f"WHERE {' AND '.join(conds)} "
                         "ORDER BY embedding <=> CAST(:emb AS vector) LIMIT :limit"),
                    params,
                ).mappings().all()
                return [{**dict(r), "text": (dict(r).get("text") or "")[:600]} for r in rows]
            finally:
                db.close()

        try:
            out = _guarded(do_chunks, default=[])
            _cache_set(("semantic_chunks", query, limit, category, skill), out)
            return out
        except Exception:
            return []
    except Exception:
        return []


def _db_rows(table: str, where: str, params: dict, limit: int) -> list[dict] | None:
    """Best-effort DB read. None when KB off, DB down, or tables missing."""
    if not _kb_enabled():
        return None
    key = (table, where, tuple(sorted((k, str(v)) for k, v in params.items())), limit)
    cached, val = _cache_get(("db_rows",) + key)
    if cached:
        return val  # type: ignore[return-value]
    try:
        from app.db.session import get_session
        from sqlalchemy import text

        db = get_session()

        def do_rows():
            try:
                rows = db.execute(
                    text(f"SELECT * FROM {table} WHERE {where} LIMIT :limit"),
                    {**params, "limit": limit},
                ).mappings().all()
                return [dict(r) for r in rows]
            finally:
                db.close()

        try:
            out = _guarded(do_rows, default=None)
            _cache_set(("db_rows",) + key, out)
            return out
        except Exception:
            return None
    except Exception:
        return None


def get_resources(skills: list[str], limit_per_skill: int = 3) -> dict[str, list[dict]]:
    """Curated-first resources per skill: docs + video + course/practice.

    DB rows (seeded from this same data) win when reachable; the curated
    fallback keeps every run working offline.
    """
    out: dict[str, list[dict]] = {}
    for skill in skills or []:
        db_rows = _db_rows("learning_resources", "skill = :skill",
                           {"skill": skill}, limit_per_skill)
        if db_rows:
            out[skill] = [{"title": r.get("title", ""), "url": r.get("url", ""),
                           "type": r.get("type", "docs")} for r in db_rows]
            continue
        sem = semantic_search("learning_resources", f"Learn {skill} tutorial",
                              limit_per_skill)
        if sem:
            out[skill] = [{"title": r.get("title", ""), "url": r.get("url", ""),
                           "type": r.get("type", "docs")} for r in sem]
        else:
            out[skill] = [dict(r) for r in RESOURCES if r["skill"] == skill][:limit_per_skill]
    return out


def get_questions(skills: list[str], limit: int = 12) -> list[dict]:
    """Interview questions for skills (+HR). DB first, curated fallback."""
    if not skills:
        general = [dict(q) for q in QUESTIONS if q["skill"] == "General"]
        if _kb_enabled():
            db_rows = _db_rows("question_bank", "skill = :skill",
                               {"skill": "General"}, limit)
            if db_rows:
                return [{"skill": "General", "category": r.get("category", "hr"),
                         "difficulty": r.get("difficulty", "Easy"),
                         "q": r.get("q", ""), "ideal_answer": r.get("ideal_answer", ""),
                         "key_points": r.get("key_points", [])} for r in db_rows][:limit]
        return general[:limit]
    per = max(limit // max(len(skills), 1), 1)
    out: list[dict] = []
    for skill in skills:
        db_rows = _db_rows("question_bank", "skill = :skill", {"skill": skill}, per)
        if db_rows:
            out.extend({"skill": r.get("skill", skill),
                        "category": r.get("category", "technical"),
                        "difficulty": r.get("difficulty", "Medium"),
                        "q": r.get("q", ""), "ideal_answer": r.get("ideal_answer", ""),
                        "key_points": r.get("key_points", [])} for r in db_rows)
            continue
        sem = semantic_search("question_bank", f"{skill} interview questions", per)
        if sem:
            out.extend({"skill": r.get("skill", skill),
                        "category": r.get("category", "technical"),
                        "difficulty": r.get("difficulty", "Medium"),
                        "q": r.get("q", ""), "ideal_answer": r.get("ideal_answer", ""),
                        "key_points": r.get("key_points", [])} for r in sem)
        else:
            out.extend(dict(q) for q in QUESTIONS if q["skill"] == skill)
    if len(out) < limit:
        out.extend(dict(q) for q in QUESTIONS if q["skill"] == "General")
    return out[:limit]


def get_rag_questions(skills: list[str], per_skill: int = 2,
                      category: str = "technical") -> list[dict]:
    """RAG-first Q&A retrieval from ingested PDF chunks.

    For each skill: skill-filtered vector search, then unfiltered search,
    then parse Q&A pairs out of the chunk text. Returns
    [{skill, q, a, source, page}]. [] when KB is off/unavailable — callers
    fall through to bank questions, then templates, then (last) the LLM.
    """
    from app.tools import pdf_ingest

    parse = pdf_ingest.parse_hr_qa if category == "hr" else pdf_ingest.parse_tech_qa
    out: list[dict] = []
    seen: set[str] = set()
    for skill in skills or []:
        hits = semantic_chunks(f"{skill} interview questions and answers",
                               limit=3, category=category, skill=skill)
        if not hits:
            hits = semantic_chunks(f"{skill} interview questions and answers",
                                   limit=3, category=category)
        for hit in hits:
            for pair in parse(hit.get("text", "")):
                key = pair["q"][:120].lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append({"skill": skill, "q": pair["q"], "a": pair["a"],
                            "source": hit.get("source", ""), "page": hit.get("page")})
                if len([o for o in out if o["skill"] == skill]) >= per_skill:
                    break
    return out


def get_rag_hr_questions(limit: int = 8) -> list[dict]:
    """RAG-first HR Q&A from the ingested HR PDF (OCR chunks)."""
    from app.tools import pdf_ingest

    out: list[dict] = []
    seen: set[str] = set()
    for query in ("HR behavioral interview questions and best answers",
                  "tell me about yourself strengths weaknesses teamwork failure"):
        for hit in semantic_chunks(query, limit=4, category="hr"):
            for pair in pdf_ingest.parse_hr_qa(hit.get("text", "")):
                key = pair["q"][:120].lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append({"skill": "General", "q": pair["q"], "a": pair["a"],
                            "source": hit.get("source", ""), "page": hit.get("page")})
                if len(out) >= limit:
                    return out
    return out


def kb_counts() -> dict:
    return {"resources": len(RESOURCES), "questions": len(QUESTIONS)}

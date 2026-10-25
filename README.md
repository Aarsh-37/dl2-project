# CareerPilot AI — From Resume to Offer

> **Tagline:** "From Resume to Offer — Autopilot Your Career"

CareerPilot AI is a hybrid agentic-AI career platform. Upload a **resume + job description** once, and a LangGraph-orchestrated agent pipeline streams back **six outputs**: ATS score, skill gaps, a day-wise learning roadmap with video tutorials, tech + HR interview prep (grounded in your own material), a tailored 1-page resume (PDF/LaTeX/DOCX), and matched job listings.

**Core design rule:** *Python scores, LLMs explain.* Deterministic code does parsing, extraction, scoring, matching, and validation (millisecond-fast, free, factual). LLMs do only reasoning, planning, and writing — every LLM step has a deterministic fallback, so the app works even with no API keys.

---

## 1. Functionalities

| # | Feature | What it does | Key point |
|---|---|---|---|
| 1 | **ATS score as per JD** | Deterministic engine (keyword + skill + semantic + experience + education + project relevance → 0–100) + LLM-written rationale, strengths, gaps, quick wins | Engine never re-scored by the LLM; boundary-aware keyword matching (`Go` ≠ `Django`) |
| 2 | **Skill-gap analysis** | Strong / Partial / Missing × Required / Preferred, criticality, weeks-to-learn; fuzzy near-miss detection (`NodeJS` ~ `Node.js` → partial, not a harsh gap); experimental VAE latent skill suggestions | Invariant enforced: nothing in both strong and missing |
| 3 | **Day-wise learning roadmap** | Hours-per-day-aware plan (e.g. 14 days at 4h/day): per-day topics, hands-on practice, docs + **video tutorial** + course links, revision + mock + final-revision days, daily time-allocation table | URLs come only from the knowledge base — invented links are stripped and replaced |
| 4 | **Interview prep + mock eval** | 12 technical (Easy/Med/Hard, every required skill covered, project + architecture questions) + 8 HR, with ideal answers and follow-ups; **RAG-first**: questions/solutions pulled from your ingested PDFs, LLM fires only for uncovered skills; `POST /mock/answer` scores practice answers on a rubric | Source chips show which PDF each question came from |
| 5 | **Resume optimization + export** | Constrained LLM summary (facts only) → hallucination validator (PASS/REJECT, ≤2 retries) → human Approve/Edit → 1-page LaTeX resume (same format, JD-prioritized order, no fabricated content, no upskill section) | Page count verified by compile → count → tighten loop |
| 6 | **Job discovery + matching** | Adzuna feed (needs keys; search links until then), Python skill/semantic matching, LLM explains top picks only | Never gated behind resume approval |
| 7 | **Career coach** | Final synthesizer: top fixes + roadmap order + validation + matches | Never overrides upstream facts |
| 8 | **Verbose trace** | Every LLM call logged (task/provider/model/latency/live-or-fallback) and shown in the UI's Verbose tab | Full transparency into agentic execution |

---

## 2. Tech stack

**Frontend** (`frontend/`, Next.js on `:3001`)

| Layer | Technology |
|---|---|
| Framework | Next.js 15 + React 19 + TypeScript |
| Styling | Tailwind CSS, shadcn-style UI components, Lucide icons |
| State / data | Zustand, TanStack Query (React Query) |
| Forms / validation | React Hook Form + Zod (mirrors backend contracts) |
| Charts | Recharts (ATS donut, breakdown bars) |
| Streaming | fetch + ReadableStream SSE (no EventSource — custom headers work) |
| Tests | Vitest (unit), Playwright (e2e smoke) |

**Backend** (`backend/`, FastAPI on `:8010`)

| Layer | Technology |
|---|---|
| API | FastAPI + Pydantic v2 + Uvicorn |
| Orchestration | **LangGraph** (state graph, routing, bounded retries, Postgres checkpointer, HITL interrupt) |
| LLM router | Custom httpx client: **OpenRouter → Groq → Ollama** failover chain, per-task temperature/timeout/token budgets, JSON-repair retries, local `careerpilot` Ollama model (Modelfile persona) |
| Parsing | PyMuPDF → pdfplumber → Tesseract OCR (+ Pillow, python-docx) |
| NLP / ML | spaCy NER, regex extractors, 300-skill taxonomy, **Sentence Transformers** (`all-MiniLM-L6-v2`), **PyTorch VAE** skill recommender |
| RAG store | Supabase Postgres + **pgvector** (`learning_resources`, `question_bank`, `kb_chunks` with embeddings + metadata) |
| DB / ORM | SQLAlchemy 2 + Alembic (m1 core, m2 KB, m3 chunks), Supabase Auth + Storage buckets |
| Resume export | LaTeX (Jake-style template, pdflatex/MiKTeX) with reportlab + python-docx fallback |
| Jobs | Adzuna API (JSearch optional P2) |
| Tests | pytest (85 tests) |

**Infrastructure:** Docker Compose (local pgvector Postgres), Supabase (managed Postgres + Auth + Storage), Ollama (local `llama3.2` + custom `careerpilot` model). Target deploys: Vercel (frontend) + Render (backend). Baseline cost: **₹0** (free tiers + local models).

---

## 3. Architecture

```
 USER → Next.js (:3001) → FastAPI (:8010) → LangGraph Orchestrator
   → Resume Agent + JD Agent → Profile Normalizer (single source of truth)
   → ATS Engine (Python) → ATS Explainer (LLM, never re-scores)
   → Skill Gap (+ VAE suggestions) → ┬ Roadmap (LLM + RAG resources) ──┐
                                       └ Interview Gen (RAG-first) ─────┘
   → ┬ Resume Optimizer → Validator → ┬ REJECT → Optimizer (retry ≤2)
     │                                └ PASS → Human Approval (HITL)
     └ Job Discovery (Adzuna) → Job Matching (Python) ─────────────────┐
   → Career Coach → result + agent_trace → streamed to UI
```

**RAG pipeline** (`data/kb/*.pdf` → app):
`PDF → page text (/OCR) → 800/100 overlapping chunks → ST embeddings → kb_chunks (embedding + text + source/skill/page)` → cosine retrieval grounds interview questions, roadmap resources (`learning_resources.csv`: docs + YouTube link for all 262 taxonomy skills), and the question bank. User CSVs in `data/kb/` seed the same tables idempotently.

**Request flow:** `POST /analyze` (multipart) → `202 {job_id, stream_url}` → graph runs (roadmap ∥ interview in parallel) → `GET /result/{job_id}` (full §5.1 payload) → `GET /stream/{job_id}` replays progress events → `POST /resumes/export` (pdf/tex/docx), `POST /mock/answer`, `POST /resumes/approve`, `GET /history`, `DELETE /result/{job_id}`.

**Single source of truth:** normalized candidate profile → ATS, gaps, roadmap, interview, jobs, coach never disagree. Shared `agent_trace` + `errors` arrays make every run debuggable from the Verbose tab.

---

## 4. Project structure

```
CareerPilot AI/
├── README.md                  ← you are here
├── contracts.md               ← frozen: state keys, weights, SSE events
├── agents.md / roadmap.md / database.md / backend.md / frontend.md / tasks.md
├── .env / .env.example        ← secrets + LLM chain + DB URLs (never commit .env)
├── start-backend.bat / start-frontend.bat   ← one-click dev servers (Windows)
├── docker-compose.yml         ← local pgvector Postgres + API
├── requirements.txt           ← full backend stack
├── backend/
│   ├── app/{api,agents,core,db,models,services,tools,utils,workflows}/
│   ├── app/core/llm.py        ← provider chain + budgets + trace logging
│   ├── alembic/versions/      ← m1_core, m2_kb, m3_kb_chunks
│   ├── scripts/               ← check_supabase, seed_kb, backfill_embeddings,
│   │                            ingest_pdfs, train_skill_vae, build_learning_csv
│   ├── ollama/Modelfile       ← `ollama create careerpilot -f ...`
│   └── tests/                 ← pytest suite (68 tests)
├── frontend/
│   ├── app/{analyze,results/[jobId],history,jobs}/
│   ├── components/{ats,gaps,roadmap,interview,resume,jobs,verbose,...}/
│   └── lib/{api,schemas,store,useAnalysis,useStream}.ts
└── data/
    ├── skill_taxonomy.csv     ← ~300 skills, alias resolution
    ├── samples/               ← sample resume/JD pairs + eval fixtures
    ├── eval/eval_set.csv      ← human-labeled ATS eval pairs
    ├── kb/*.pdf               ← ingested prep material (skills + HR Q&A)
    └── kb/*.csv               ← learning resources + questions (seeded to DB)
```

---

## 5. Prerequisites

| Need | Why | Install / get |
|---|---|---|
| Python 3.11+ | Backend | python.org |
| Node.js 18+ | Frontend | nodejs.org |
| Ollama + `llama3.2` | Local LLM (free, offline) | `ollama pull llama3.2`, then `ollama create careerpilot -f backend/ollama/Modelfile` |
| Supabase project | Postgres + pgvector + Auth + Storage | supabase.com (free): run `CREATE EXTENSION vector; CREATE EXTENSION "pgcrypto";`, create private buckets `resumes`, `generated` |
| MiKTeX / TeX Live *(optional)* | Real LaTeX resume PDFs (reportlab fallback otherwise) | miktex.org |
| Tesseract OCR *(optional)* | Scanned-PDF ingestion | tesseract-ocr builds |
| API keys *(optional — app degrades gracefully)* | `OPENROUTER_API_KEY` / `GROQ_API_KEY` (fast cloud LLMs), `ADZUNA_APP_ID/KEY` (live jobs) | openrouter.ai, console.groq.com, adzuna.com |

---

## 6. Steps to run the project

```bash
# 0. Clone / open the folder, then configure secrets:
cp .env.example .env        # Windows: copy .env.example .env
# Fill .env: Supabase URL/keys, DATABASE_URL_POOLER/DIRECT,
# LLM keys (or leave empty for Ollama-only), Adzuna keys (or leave for search links)

# 1. Backend (terminal 1, from CareerPilot AI/backend/)
pip install -r ../requirements.txt
alembic upgrade head              # m1+m2+m3 tables + RLS + skill seed
python scripts/seed_kb.py         # learning resources + question bank
python scripts/ingest_pdfs.py --source skills   # RAG chunks (text PDF, fast)
python scripts/ingest_pdfs.py --source hr       # RAG chunks (OCR, ~10 min)
python scripts/backfill_embeddings.py           # vector-embed anything missed
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
# → API live at http://localhost:8010  (docs at /docs)

# 2. Frontend (terminal 2, from CareerPilot AI/frontend/)
npm install
npm run dev
# → UI live at http://localhost:3001

# 3. Test it: open :3001 → Analyze → paste resume + JD (≥50 chars each)
#    → watch progress → ATS / Gaps / Roadmap / Interview / Resume / Jobs tabs.
```

Windows shortcut: double-click **`start-backend.bat`**, then **`start-frontend.bat`** (servers don't survive sleep — rerun the bats if the UI says "Failed to fetch").

Useful checks: `python scripts/check_supabase.py` (DB readiness report), `pytest tests/ -q` (backend suite, 85 tests), `npx tsc --noEmit` (frontend types), `ollama list` (local models).

Key env knobs (`root .env`): `LLM_PRIMARY=openrouter` + `LLM_FALLBACKS=groq,ollama` (failover order), `LLM_CALL_BUDGET=55` (seconds per LLM call max), `CAREERPILOT_LLM=0` (force deterministic/offline), `CAREERPILOT_KB=0` (skip DB KB reads), `CAREERPILOT_GRAPH=0` (plain pipeline instead of LangGraph), `CAREERPILOT_SEMANTIC=1` (ST semantic ATS component).

---

## 7. Current status & known limits (honest)

**Working and verified:** all six outputs end-to-end, RAG retrieval over your PDFs, Supabase persistence, resume PDF/TeX/DOCX export, mock eval, history/delete, verbose trace, 68 green tests.

**Still pending:** live Adzuna feed (needs your keys — search links until then); Supabase JWT auth (interim `X-User-Id` header — fine for testing, not production); 20-pair human eval labels (3/20 done); CI workflow + Vercel/Render deploys + demo video/report. Single-worker dev server: run one analysis at a time (long Ollama generations block other requests). First run is slow (models load into RAM once, then fast).

# CareerPilot AI — Backend (Phase 1: core, no DB)

Pure-Python core: `app/tools/` (parsing, skill extraction) + `app/services/`
(gap function, ATS engine). No database, no network, no LLM.

## Run

```bash
cd backend
python -m pytest tests -q   # core tests (persistence needs TEST_DATABASE_URL, else skipped)
python scripts/demo_core.py  # Demo 1: ATS + gaps for the 3 sample pairs
alembic upgrade head --sql   # review m1 offline before applying
alembic upgrade head         # apply m1 (needs DATABASE_URL_DIRECT)
```

PDF/DOCX/OCR dependencies install from `requirements.txt` but are imported
lazily — text/markdown fixtures and the full test suite run on stdlib alone.

## What lives here (per backend.md §2)

Done: `core/config`, `utils/text_clean`, `tools/{resume_parser,jd_parser,skill_extract}`,
`services/{gap_service,ats_service,analysis_service}`, `models/` (m1),
`db/session`, `alembic/` (m1 with RLS + skills seed), `tests/`, `scripts/demo_core.py`.
Deferred to later phases: `tools/embeddings` (Phase 2), m2/m3 migrations,
`api/` plain functions then LangGraph (Phase 4), `agents/` + LLM nodes (Phase 5–6).

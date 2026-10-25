"""PDF ingest tests: chunking + skill tagging (pure functions, offline)."""
from app.tools import pdf_ingest


def test_chunk_overlap_and_determinism():
    text = "\n".join(f"line {i} " + ("x" * 60) for i in range(60))
    a = pdf_ingest.chunk_text(text, size=800, overlap=100)
    b = pdf_ingest.chunk_text(text, size=800, overlap=100)
    assert a == b and len(a) > 2
    assert all(len(c) <= 800 for c in a)
    # Overlap: consecutive chunks share text.
    assert any(a[i][-50:] in a[i + 1] for i in range(len(a) - 1))
    assert pdf_ingest.chunk_text("") == []
    assert pdf_ingest.chunk_text("short") == ["short"]


def test_skill_tagging_with_taxonomy():
    tax = {"terms": {"docker": "Docker", "react": "React"}, "category": {}}
    pages = pdf_ingest.tag_skill_pages([
        {"page": 1, "text": "Contents\n1. Python\n2. Docker", "ocr": False},
        {"page": 2, "text": "12. Docker\nQ1. What is a container?\nAnswer: isolated env.", "ocr": False},
        {"page": 3, "text": "Q2. Images vs containers?\nAnswer: templates vs instances.", "ocr": False},
    ], tax)
    assert pages[1]["skill"] == "Docker"  # taxonomy canonical
    assert pages[2]["skill"] == "Docker"  # carried over, Q-lines never headings


def test_skill_tagging_keeps_raw_when_unmapped():
    pages = pdf_ingest.tag_skill_pages([
        {"page": 1, "text": "7. SomeNewTech\nQ1. What?\nAnswer: this.", "ocr": False},
    ], {"terms": {}, "category": {}})
    assert pages[0]["skill"] == "SomeNewTech"


def test_boilerplate_cleaned():
    pages = pdf_ingest.tag_skill_pages([
        {"page": 1, "text": "Q1. What is Docker?\nAnswer: platform.", "ocr": False},
    ], None)
    assert pages[0].get("skill") is None


def test_semantic_chunks_off_without_kb():
    from app.services import kb_service as kb

    assert kb.semantic_chunks("docker interview") == []  # CAREERPILOT_KB=0 in conftest


def test_build_rows_skills_pdf():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import ingest_pdfs

    rows = ingest_pdfs.build_rows("skills")
    assert len(rows) > 200
    assert all(r["text"] and r["category"] == "technical" for r in rows)
    skills = {r["skill"] for r in rows}
    assert "Docker" in skills and "Python" in skills
    assert all(isinstance(r["chunk_index"], int) for r in rows)

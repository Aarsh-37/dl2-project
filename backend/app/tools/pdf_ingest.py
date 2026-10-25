"""PDF ingest primitives for the RAG pipeline (deterministic, no LLM).

Pipeline per PDF: pages -> text per page (PyMuPDF, pdfplumber, then OCR) ->
skill tagging from section headings -> overlapping char chunks, each
carrying {page, skill, category} metadata. Embeddings happen in
scripts/ingest_pdfs.py (batched ST) so this module stays dependency-light.
"""
from __future__ import annotations

import re
from pathlib import Path

# Skill section headings like "12. Docker" (NOT question lines like "Q1.").
_SKILL_HEADING = re.compile(r"^(\d{1,3})\.\s+([A-Za-z][A-Za-z0-9+_#./\- ]{1,40})$")
# Boilerplate lines that pollute chunks.
_BOILERPLATE = re.compile(
    r"^(100 Skills Interview Questions & Answers|64 Toughest Questions|Page \d+|Contents)$",
    re.I,
)


def extract_pages(path: str | Path, ocr_dpi: int = 150,
                  start_page: int = 1, limit_pages: int = 0) -> list[dict]:
    """Return [{page (1-based), text, ocr: bool}]. Never raises on odd PDFs.

    start_page/limit_pages restrict RENDERED pages (1-based) so long OCR
    documents can be ingested in halves; page numbers stay global.
    """
    pages: list[dict] = []
    try:
        import fitz
    except ImportError:
        return pages
    doc = fitz.open(path)
    total = len(doc)
    lo = max(start_page, 1)
    hi = total if not limit_pages else min(total, lo - 1 + limit_pages)
    for num in range(lo, hi + 1):
        page = doc[num - 1]
        text = (page.get_text() or "").strip()
        ocr = False
        if len(text) < 50:
            text = _plumber_page(path, num) or _ocr_page(page, ocr_dpi)
            ocr = bool(text)
        pages.append({"page": num, "text": _clean(text), "ocr": ocr})
    return pages


def _plumber_page(path: str | Path, num: int) -> str:
    try:
        import pdfplumber
    except ImportError:
        return ""
    try:
        with pdfplumber.open(path) as pdf:
            if 1 <= num <= len(pdf.pages):
                return (pdf.pages[num - 1].extract_text() or "").strip()
    except Exception:
        pass
    return ""


def _ocr_page(page, dpi: int) -> str:
    try:
        from PIL import Image  # noqa: F401
        import io
        import pytesseract
    except ImportError:
        return ""
    try:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return (pytesseract.image_to_string(img) or "").strip()
    except Exception:
        return ""


def _clean(text: str) -> str:
    lines = [l.rstrip() for l in (text or "").replace("\r\n", "\n").split("\n")]
    # Drop dotted TOC leaders ("Question text.............. 26") and footers.
    out = []
    for line in lines:
        line = re.sub(r"\.{3,}\s*\d*\s*$", "", line).strip()
        if line and not _BOILERPLATE.match(line):
            out.append(line)
    return "\n".join(out).strip()


def tag_skill_pages(pages: list[dict], taxonomy: dict | None = None) -> list[dict]:
    """Walk pages tracking the current `N. Skill` heading; resolve each skill
    to its taxonomy canonical name (keeps the raw heading when unmapped)."""
    terms = (taxonomy or {}).get("terms", {})
    current: str | None = None
    for page in pages:
        for line in page["text"].split("\n"):
            match = _SKILL_HEADING.match(line.strip())
            if match and not line.strip().upper().startswith("Q"):
                raw = match.group(2).strip()
                key = raw.lower()
                current = terms.get(key, terms.get(key.rstrip("s"), raw))
                page["skill"] = current
                break
        page.setdefault("skill", current)
    return pages


def chunk_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    """Overlapping char windows (deterministic). Keeps Q&A pairs together by
    preferring splits at newlines near the window edge."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            edge = text.rfind("\n", start + size - overlap, end)
            if edge > start:
                end = edge
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


_Q_SPLIT = re.compile(r"(?m)^Q(\d{1,3})\.\s*")
_HR_SPLIT = re.compile(r"Question\s+(\d{1,3})\b")


def _squash(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    text = text.replace("�", "").replace("|", "I")
    return re.sub(r"\s+", " ", text).strip()


def parse_tech_qa(text: str) -> list[dict]:
    """Extract [{q, a}] from skills-PDF chunks: `Q1. ... Answer: ...` blocks.

    Pure function — the backbone of RAG-first interview prep: retrieved
    passages become questions+solutions with zero LLM cost.
    """
    out: list[dict] = []
    text = re.sub(r"(?<=[.!?])\s+(?=Q\d{1,3}\.)", "\n", text or "")
    parts = _Q_SPLIT.split(text)
    # split() yields [pre, num1, body1, num2, body2, ...]
    for i in range(1, len(parts), 2):
        body = parts[i + 1] if i + 1 < len(parts) else ""
        if "Answer:" in body:
            q_raw, a_raw = body.split("Answer:", 1)
        else:
            continue  # incomplete pair — skip rather than invent
        q, a = _squash(q_raw), _squash(a_raw)
        if len(q) >= 8 and len(a) >= 20:
            out.append({"q": q[:500], "a": a[:2000]})
    return out


def parse_hr_qa(text: str) -> list[dict]:
    """Extract [{q, a}] from HR-PDF (OCR) chunks: `Question N ...` headers
    with TRAPS:/BEST ANSWER: bodies. Tolerates OCR noise; skips fragments."""
    out: list[dict] = []
    parts = _HR_SPLIT.split(text or "")
    for i in range(1, len(parts), 2):
        body = parts[i + 1] if i + 1 < len(parts) else ""
        head, answer = body, ""
        if "BEST ANSWER:" in body:
            head, answer = body.split("BEST ANSWER:", 1)
        elif "TRAPS:" in body:
            head, answer = body.split("TRAPS:", 1)
        head = re.split(r"TRAPS:|BEST ANSWER:", head, maxsplit=1)[0]
        q = _squash(re.sub(r"\.{2,}.*$", "", head)[:300])
        a = _squash(answer)
        if len(q) >= 10 and len(a) >= 60:
            out.append({"q": q[:500], "a": a[:2000]})
    return out

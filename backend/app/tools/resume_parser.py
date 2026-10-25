"""Deterministic resume parsing. No LLM, no DB. Stdlib-only at import time.

Chain: PyMuPDF -> pdfplumber -> OCR (Tesseract+Pillow) -> raise with install hint.
Plain-text/markdown fixtures parse without any third-party dependency.
"""
from pathlib import Path

from app.utils.text_clean import clean_text


def parse_text(text: str, source: str = "text") -> dict:
    return {"text": clean_text(text), "source": source}


def parse_file(path: str | Path) -> dict:
    """Dispatch by suffix. Unknown suffixes are read as plain text."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(p)
    if suffix == ".docx":
        return parse_docx(p)
    return {
        "text": clean_text(p.read_text(encoding="utf-8", errors="ignore")),
        "source": suffix.lstrip(".") or "text",
        "path": str(p),
    }


def parse_pdf(path: str | Path) -> dict:
    p = Path(path)
    text = _try_pymupdf(p)
    if text.strip():
        return {"text": clean_text(text), "source": "pdf", "path": str(p)}
    text = _try_pdfplumber(p)
    if text.strip():
        return {"text": clean_text(text), "source": "pdf-fallback", "path": str(p)}
    text = _ocr_pdf(p)
    if text.strip():
        return {"text": clean_text(text), "source": "pdf-ocr", "path": str(p)}
    raise RuntimeError(f"No text extracted from {p} (not even via OCR).")


def _try_pymupdf(p: Path) -> str:
    try:
        import fitz
    except ImportError:
        return ""
    with fitz.open(p) as doc:
        return "\n".join(page.get_text() for page in doc)


def _try_pdfplumber(p: Path) -> str:
    try:
        import pdfplumber
    except ImportError:
        return ""
    parts: list[str] = []
    with pdfplumber.open(p) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _ocr_pdf(p: Path) -> str:
    try:
        import fitz
        from PIL import Image  # noqa: F401 (ensures Pillow present)
        import pytesseract
    except ImportError:
        return ""
    import io

    parts: list[str] = []
    with fitz.open(p) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            parts.append(pytesseract.image_to_string(img))
    return "\n".join(parts)


def parse_docx(path: str | Path) -> dict:
    try:
        import docx
    except ImportError as exc:
        raise RuntimeError("python-docx is required for .docx files.") from exc
    p = Path(path)
    document = docx.Document(p)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    return {"text": clean_text(text), "source": "docx", "path": str(p)}

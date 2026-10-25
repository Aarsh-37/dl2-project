"""Small text helpers shared by the parsers. Stdlib only."""
import re

_WS_LINE = re.compile(r"[ \t]+")
_BLANK_RUN = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """Normalize line endings/whitespace. Never raises on odd input."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WS_LINE.sub(" ", text)
    text = _BLANK_RUN.sub("\n\n", text)
    return text.strip()


def section_text(text: str, heading: str) -> str:
    """Return the markdown section under a `## <heading>` header (case-insensitive).

    Captures until the next `## ` header or end of text. Returns "" if absent.
    """
    lines = text.split("\n")
    capture: list[str] = []
    inside = False
    target = heading.strip().lower()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            title = stripped[3:].strip().lower()
            inside = target in title
            continue
        if inside:
            capture.append(line)
    return "\n".join(capture).strip()


def chunk_text(text: str, size: int = 400, overlap: int = 50) -> list[str]:
    """Char-window chunking for document_chunks (embeddings backfilled later)."""
    text = clean_text(text).replace("\n", " ")
    if not text:
        return []
    if size <= 0:
        raise ValueError("size must be positive")
    step = max(size - overlap, 1)
    return [text[i:i + size] for i in range(0, len(text), step)]

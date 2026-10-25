"""Embeddings: ST all-MiniLM-L6-v2 local, chunk 400/50, cached by SHA256.

Returns None when sentence-transformers is absent — ats_engine renormalizes.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache

_model = None


def sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def chunk(text: str, size: int = 400, overlap: int = 50) -> list[str]:
    words = (text or "").split()
    if not words:
        return []
    out, i = [], 0
    while i < len(words):
        out.append(" ".join(words[i:i + size]))
        i += size - overlap
    return out


@lru_cache(maxsize=512)
def _embed_cached(text_hash: str, text: str) -> tuple[float, ...] | None:  # noqa: ARG001
    global _model
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    vec = _model.encode([text], convert_to_tensor=False)[0]
    return tuple(float(x) for x in vec)


def embed(text: str) -> list[float] | None:
    v = _embed_cached(sha256(text), text or "")
    return list(v) if v else None


def cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    den = (sum(x * x for x in a) ** 0.5) * (sum(y * y for y in b) ** 0.5)
    return round(100 * num / den, 1) if den else 0.0


def semantic_score(resume_text: str, jd_text: str) -> float | None:
    a, b = embed(resume_text or ""), embed(jd_text or "")
    return cosine(a, b) if a and b else None

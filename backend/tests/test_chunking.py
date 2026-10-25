"""Chunking unit tests (pure Python, no DB)."""
from app.utils.text_clean import chunk_text


def test_empty_text_has_no_chunks():
    assert chunk_text("") == []


def test_short_text_is_one_chunk():
    assert chunk_text("hello world") == ["hello world"]


def test_windows_overlap_and_cover_all_text():
    text = "abcdefghij"
    chunks = chunk_text(text, size=4, overlap=2)
    assert chunks[0] == "abcd"
    assert all(len(c) <= 4 for c in chunks)
    # step = size - overlap = 2, so each window starts 2 chars after the last
    assert chunks[1] == "cdef"
    assert chunks[2] == "efgh"
    # every character is covered by at least one window
    covered = set()
    for start in range(0, len(text), 4 - 2):
        covered.update(range(start, min(start + 4, len(text))))
    assert covered == set(range(len(text)))

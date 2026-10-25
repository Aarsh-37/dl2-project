"""Resilience tests: shared engine, bounded DB calls, offline fallbacks."""
import time

from app.db import session as sess
from app.services import kb_service as kb


def test_pooler_engine_is_singleton():
    assert sess.pooler_engine() is sess.pooler_engine()


def test_bounded_returns_default_on_hang():
    import threading

    block = threading.Event()

    def hang():
        block.wait(timeout=60)
        return "never"

    t0 = time.monotonic()
    assert kb._bounded(hang, default=None, timeout=2) is None
    assert time.monotonic() - t0 < 20


def test_kb_reads_degrade_offline(monkeypatch):
    monkeypatch.setenv("CAREERPILOT_KB", "0")
    assert kb._db_rows("skills", "name = :n", {"n": "Python"}, 5) is None
    assert kb.semantic_search("learning_resources", "docker", 3) is None
    assert kb.semantic_chunks("docker", 3) == []
    assert kb.get_rag_questions(["Docker"]) == []


def test_circuit_opens_after_consecutive_failures():
    kb._CIRCUIT["fails"] = 0
    kb._CIRCUIT["skip_until"] = 0.0
    assert kb._circuit_ok()
    kb._circuit_note(False)
    kb._circuit_note(False)
    assert kb._circuit_ok()  # 2 fails: still trying
    kb._circuit_note(False)
    assert not kb._circuit_ok()  # 3rd fail: circuit open
    kb._circuit_note(True)
    assert kb._circuit_ok()  # success resets


def test_guarded_skips_db_when_circuit_open(monkeypatch):
    monkeypatch.setenv("CAREERPILOT_KB", "1")
    kb._CIRCUIT["fails"] = 3
    import time as _t
    kb._CIRCUIT["skip_until"] = _t.monotonic() + 120
    try:
        t0 = _t.monotonic()
        assert kb._guarded(lambda: 1 / 0, default="fb") == "fb"
        assert _t.monotonic() - t0 < 5  # instant, no DB touched
    finally:
        kb._CIRCUIT["fails"] = 0
        kb._CIRCUIT["skip_until"] = 0.0

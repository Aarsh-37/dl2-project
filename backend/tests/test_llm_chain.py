"""Provider chain tests: order, failover, budget, key gating (offline)."""
import time

from app.core import llm as core


def _chain_llm(monkeypatch, chain, fail=None):
    """LLM whose _call_once fails for `fail` providers, succeeds otherwise."""
    fail = set(fail or [])
    llm = core.LLM(model=chain[0], task="explain")
    llm.chain = list(chain)

    def fake_call(provider, spec, prompt, httpx, timeout):
        assert timeout > 0
        if provider in fail:
            raise core.LLMError(f"{provider} boom")
        return f"ok-from-{provider}"

    monkeypatch.setattr(llm, "_call_once", fake_call)
    return llm


def test_chain_order_openrouter_first(monkeypatch):
    monkeypatch.setenv("LLM_PRIMARY", "openrouter")
    monkeypatch.setenv("LLM_FALLBACKS", "groq,ollama")
    assert core.get_chain() == ["openrouter", "groq", "ollama"]


def test_explicit_provider_heads_chain(monkeypatch):
    monkeypatch.setenv("LLM_PRIMARY", "groq")
    llm = core.LLM(model="ollama/llama3.2")
    assert llm.chain[0] == "ollama" and llm.provider == "ollama"


def test_failover_to_second_provider(monkeypatch):
    llm = _chain_llm(monkeypatch, ["openrouter", "groq", "ollama"], fail={"openrouter"})
    core.clear_call_log()
    assert llm.invoke("hi") == "ok-from-groq"
    modes = [(t["provider"], t["mode"]) for t in core.drain_call_log()]
    assert modes == [("openrouter", "error"), ("groq", "live")]


def test_all_fail_raises_last_error(monkeypatch):
    llm = _chain_llm(monkeypatch, ["groq", "ollama"], fail={"groq", "ollama"})
    try:
        llm.invoke("hi")
        raise AssertionError("should raise")
    except core.LLMError as exc:
        assert "ollama" in str(exc)


def test_missing_key_provider_skipped(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    llm = _chain_llm(monkeypatch, ["groq", "ollama"])
    assert llm.invoke("hi") == "ok-from-ollama"
    provs = [t["provider"] for t in core.drain_call_log()]
    assert provs[0] == "groq" and provs[-1] == "ollama"


def test_call_budget_caps_total_time(monkeypatch):
    llm = _chain_llm(monkeypatch, ["groq", "ollama"], fail={"groq", "ollama"})
    llm.budget = 4.0
    t0 = time.time()
    try:
        llm.invoke("hi")
    except core.LLMError:
        pass
    assert time.time() - t0 < 20


def test_openrouter_spec_uses_env_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4o")
    monkeypatch.setenv("OPENROUTER_MODEL_FAST", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    llm = core.LLM(model="openrouter", task="plan")
    assert llm._spec("openrouter")["model"] == "openai/gpt-4o"
    assert llm.available is True

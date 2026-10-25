"""Per-task model routing + output cap (offline, no network)."""
from app.core import llm as core


def test_task_tier_mapping():
    assert core.TASK_TIER["plan"] == "quality"
    assert core.TASK_TIER["interview"] == "quality"
    assert core.TASK_TIER["optimize"] == "quality"
    assert core.TASK_TIER["explain"] == "fast"
    assert core.TASK_TIER["coach"] == "fast"


def test_fast_tier_uses_fast_model(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL", "big-model")
    monkeypatch.setenv("GROQ_MODEL_FAST", "small-model")
    assert core._default_model("groq", "explain") == "small-model"
    assert core._default_model("groq", "plan") == "big-model"


def test_fast_tier_falls_back_when_unset(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL", "big-model")
    monkeypatch.setenv("GROQ_MODEL_FAST", "")
    assert core._default_model("groq", "explain") == "big-model"


def test_get_llm_picks_model_per_task(monkeypatch):
    monkeypatch.setenv("LLM_PRIMARY", "groq")
    monkeypatch.setenv("GROQ_MODEL", "big-model")
    monkeypatch.setenv("GROQ_MODEL_FAST", "small-model")
    assert core.get_llm("explain").model == "small-model"
    assert core.get_llm("interview").model == "big-model"


def test_max_tokens_caps_generation(monkeypatch):
    monkeypatch.setenv("LLM_PRIMARY", "groq")
    assert core.get_llm("interview")._max_tokens() == 2500  # plan/interview headroom
    assert core.get_llm("explain")._max_tokens() == 500
    llm = core.get_llm("interview")
    llm.options["num_predict"] = 99999
    assert llm._max_tokens() == 3500  # clamped to endpoint ceiling


def test_per_task_provider_override(monkeypatch):
    monkeypatch.setenv("LLM_PRIMARY", "groq")
    monkeypatch.setenv("LLM_TASK_PROVIDERS", "interview=nvidia")
    monkeypatch.setenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
    llm = core.get_llm("interview")
    assert llm.provider == "nvidia"
    assert llm.model == "meta/llama-3.3-70b-instruct"
    assert llm.chain[0] == "nvidia"          # override first, then failover
    assert core.get_llm("explain").provider == "groq"
    assert core.get_llm("optimize").provider == "groq"


def test_nvidia_openai_endpoint(monkeypatch):
    monkeypatch.setenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1/")
    url, headers = core._chat_endpoint("nvidia", "nvapi-test")
    assert url == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert headers["Authorization"] == "Bearer nvapi-test"


def test_gpt_oss_payload_gets_low_reasoning(monkeypatch):
    monkeypatch.setenv("LLM_PRIMARY", "groq")
    llm = core.get_llm("explain")
    p = llm._chat_payload("groq", "openai/gpt-oss-20b", "hi")
    assert p["max_tokens"] == 500
    assert p["reasoning_effort"] == "low"
    # non-gpt-oss / non-groq must not carry the Groq-only param
    assert "reasoning_effort" not in llm._chat_payload("groq", "qwen/qwen3.8-27b", "hi")
    assert "reasoning_effort" not in llm._chat_payload("openrouter", "openai/gpt-4o", "hi")

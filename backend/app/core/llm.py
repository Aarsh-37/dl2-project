"""LLM router: Gemini (prod) <-> Ollama (local dev) <-> Groq/xAI/NVIDIA (fallback).

Usage:
    from app.core.llm import get_llm
    llm = get_llm("explain")          # temperature picked per task
    text = llm.invoke(prompt)         # raises LLMError on failure

    # Exact local shape you asked for also works:
    llm = LLM(model="ollama/llama3.2", base_url="http://localhost:11434", temperature=0.2)

Env:
    LLM_PRIMARY=gemini|ollama|groq|grok|xai|nvidia   (default: gemini if key else ollama)
    GEMINI_API_KEY=...            GEMINI_MODEL=gemini-2.0-flash
    GROQ_API_KEY=...              GROQ_MODEL=llama-3.3-70b-versatile
    GROK_API_KEY=... / XAI_API_KEY=...   XAI_MODEL=grok-beta
    NVIDIA_API_KEY=...            NVIDIA_MODEL=meta/llama-3.3-70b-instruct
    NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
    OLLAMA_URL=http://localhost:11434    OLLAMA_MODEL=llama3.2

    LLM_TASK_PROVIDERS="interview=nvidia,optimize=groq"  # per-agent override;
    listed agents use that provider first, then the normal failover chain.

Agents MUST catch LLMError and fall back to deterministic templates —
nodes append to errors, never raise (contracts.md).
"""
from __future__ import annotations

import json
import hashlib
import os
import re
from pathlib import Path

try:  # auto-load project-root .env so keys work without manual export
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)
except ImportError:
    pass

TASK_TEMPS = {
    "extract": 0.1,
    "jd": 0.15,
    "explain": 0.2,
    "validate": 0.25,
    "coach": 0.3,
    "plan": 0.4,
    "optimize": 0.4,
    "interview": 0.7,
}

# Per-task HTTP timeouts (seconds). CPU-local Ollama needs room for long
# generations; long outputs are split by agents so these are ceilings.
TASK_TIMEOUTS = {
    "extract": 60,
    "jd": 90,
    "explain": 90,
    "validate": 90,
    "coach": 120,
    "plan": 240,
    "optimize": 180,
    "interview": 300,
}

# Per-task Ollama generation params (llama3.2-3B on CPU tuning).
# num_predict caps runaway outputs (= wall time); num_ctx must fit prompt +
# output (interview needs headroom); top_p/repeat_penalty curb rambling.
TASK_PARAMS = {
    "extract": {"num_predict": 800, "num_ctx": 4096},
    "jd": {"num_predict": 800, "num_ctx": 4096},
    "explain": {"num_predict": 500, "num_ctx": 4096},
    "validate": {"num_predict": 400, "num_ctx": 4096},
    "coach": {"num_predict": 400, "num_ctx": 4096},
    "plan": {"num_predict": 1500, "num_ctx": 8192},
    "optimize": {"num_predict": 600, "num_ctx": 4096},
    "interview": {"num_predict": 2500, "num_ctx": 8192},
}
BASE_OPTIONS = {"top_p": 0.9, "repeat_penalty": 1.1}

# Model tier per task. "fast" = low-latency small model for short/structured
# work (a bad pick there is cheap to fall back on); "quality" = stronger model
# for long-form reasoning. Per-provider fast models come from
# {PROVIDER}_MODEL_FAST; quality falls back to {PROVIDER}_MODEL. On providers
# without a distinct fast model (e.g. Ollama) the env var is simply unset.
TASK_TIER = {
    "extract": "fast",
    "jd": "fast",
    "explain": "fast",
    "validate": "fast",
    "coach": "fast",
    "plan": "quality",
    "optimize": "quality",
    "interview": "quality",
}


class LLMError(RuntimeError):
    pass


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


# Verbose trace: every LLM attempt is logged here so the graph can attach
# it to the result as `agent_trace` and the frontend can render it.
# Drained per run (see drain_call_log); thread-safe for parallel nodes.
import threading as _threading
import time as _time

_CALL_LOG: list[dict] = []
_CALL_LOCK = _threading.Lock()


def _log_call(entry: dict) -> None:
    with _CALL_LOCK:
        _CALL_LOG.append(entry)


def drain_call_log() -> list[dict]:
    """Return logged calls since the last drain and clear the buffer."""
    with _CALL_LOCK:
        out = list(_CALL_LOG)
        _CALL_LOG.clear()
        return out


def clear_call_log() -> None:
    with _CALL_LOCK:
        _CALL_LOG.clear()


# --- prompt/response cache + provider health ------------------------------
# Identical (task, temperature, prompt) pairs are answered from memory for
# LLM_CACHE_TTL seconds. Demo runs reuse the same resume/JD, so this removes
# almost all repeat latency at zero accuracy cost (the output is identical).
_RESP_CACHE: dict[str, tuple[float, str]] = {}
_RESP_TTL = 1800.0
_RESP_MAX = 256
_CACHE_LOCK = _threading.Lock()

# Consecutive failures per fallback provider. After two failures (or an
# auth/quota error) the provider is skipped for a cooldown window, so a dead
# Ollama daemon or a drained OpenRouter account cannot add tens of seconds to
# every analysis.
_PROVIDER_FAILS: dict[str, int] = {}
_PROVIDER_SKIP_UNTIL: dict[str, float] = {}
_SKIP_SECONDS = 300.0


def _cache_get(key: str) -> str | None:
    now = _time.time()
    with _CACHE_LOCK:
        hit = _RESP_CACHE.get(key)
        if hit is None:
            return None
        ts, text = hit
        if now - ts > _RESP_TTL:
            _RESP_CACHE.pop(key, None)
            return None
        return text


def _cache_put(key: str, text: str) -> None:
    with _CACHE_LOCK:
        _RESP_CACHE[key] = (_time.time(), text)
        while len(_RESP_CACHE) > _RESP_MAX:
            _RESP_CACHE.pop(next(iter(_RESP_CACHE)))


def clear_response_cache() -> None:
    with _CACHE_LOCK:
        _RESP_CACHE.clear()


def _cache_key(task: str, temperature: float, head: str, prompt: str) -> str:
    raw = f"{task}|{temperature:.2f}|{head}|{prompt}"
    return hashlib.sha256(raw.encode("utf-8", "ignore")).hexdigest()


def _mark_failure(provider: str, primary: str, exc: BaseException) -> None:
    """Cool down dead fallbacks; never bench the primary provider."""
    msg = str(exc).lower()
    hard = any(tok in msg for tok in ("402", "401", "refused", "no connection",
                                      "insufficient", "unauthorized"))
    with _CACHE_LOCK:
        fails = _PROVIDER_FAILS.get(provider, 0) + 1
        _PROVIDER_FAILS[provider] = fails
        if provider != primary and (hard or fails >= 2):
            _PROVIDER_SKIP_UNTIL[provider] = _time.time() + (600 if hard else _SKIP_SECONDS)


def _cooling(provider: str) -> float:
    with _CACHE_LOCK:
        return max(0.0, _PROVIDER_SKIP_UNTIL.get(provider, 0.0) - _time.time())


def _mark_success(provider: str) -> None:
    with _CACHE_LOCK:
        _PROVIDER_FAILS.pop(provider, None)
        _PROVIDER_SKIP_UNTIL.pop(provider, None)


PROVIDERS = ("openrouter", "gemini", "groq", "xai", "nvidia", "ollama")

# Per-attempt ceilings (seconds). The overall LLM_CALL_BUDGET caps the
# whole chain so one call never exceeds ~1 minute total.
PROVIDER_TIMEOUTS = {
    "openrouter": 40, "gemini": 40, "groq": 40, "xai": 40,
    "nvidia": 45, "ollama": 150,
}

# Remote providers answer in ~1-4 s when healthy; a 40 s wait is almost always
# a Groq stall, not slow generation. Cap remote attempts per task so one stuck
# call cannot dominate wall time -- the agent's deterministic fallback takes
# over instead. Ollama keeps its generous ceiling (CPU inference is slow).
REMOTE_TASK_TIMEOUTS = {
    "extract": 12, "jd": 12, "explain": 18, "validate": 18, "coach": 18,
    "plan": 40, "optimize": 30, "interview": 40,
}


def _norm_provider(p: str) -> str:
    p = (p or "").strip().lower()
    return "xai" if p in {"grok", "xai"} else p


def get_chain() -> list[str]:
    """Failover order: LLM_PRIMARY then LLM_FALLBACKS (default groq,ollama)."""
    raw = [_norm_provider(_env("LLM_PRIMARY", ""))]
    raw += [_norm_provider(p) for p in _env("LLM_FALLBACKS", "groq,ollama").split(",")]
    chain = [p for p in raw if p in PROVIDERS]
    if not chain:
        chain = ["ollama"]
    return list(dict.fromkeys(chain))  # dedupe, order kept


class LLM:
    """Minimal multi-provider LLM client (httpx only, no new deps).

    Failover chain: invoke() tries each provider in self.chain order with
    per-attempt timeouts inside an overall LLM_CALL_BUDGET deadline —
    first success wins, every attempt is trace-logged.
    """

    def __init__(
        self,
        model: str = "ollama/llama3.2",
        base_url: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.2,
        timeout: int = 60,
        task: str = "explain",
        options: dict | None = None,
        chain: list[str] | None = None,
    ):
        self.temperature = temperature
        self.timeout = timeout
        self.enabled = True
        self.task = task
        self.options = dict(options or {})
        try:
            self.budget = float(_env("LLM_CALL_BUDGET", "55") or 55)
        except ValueError:
            self.budget = 55.0
        # Explicit "provider/model" wins as chain head; env chain fills rest.
        # A bare provider name ("nvidia") also means "this provider first".
        if "/" in model:
            explicit, rest = model.split("/", 1)
            explicit = _norm_provider(explicit)
        elif _norm_provider(model) in PROVIDERS:
            explicit, rest = _norm_provider(model), ""
        else:
            explicit, rest = "", model
        if explicit in PROVIDERS:
            head = [explicit]
            explicit_model = rest or None
        else:
            head, explicit_model = [], None
        self.chain = list(dict.fromkeys(head + [p for p in (chain or get_chain())]))
        primary = self.chain[0]
        self.provider = primary
        self.model = explicit_model or _default_model(primary, task)
        self.base_url = (base_url or _default_base_url(primary)).rstrip("/")
        self.api_key = api_key if api_key is not None else _default_key(primary)
        # Explicit overrides apply to the named provider only.
        self._explicit = {"model": {explicit: explicit_model} if explicit in PROVIDERS else {},
                          "key": {primary: api_key} if api_key is not None else {},
                          "base": {"ollama": base_url} if base_url else {}}

    def _spec(self, provider: str) -> dict:
        exp = self._explicit
        model = (exp["model"].get(provider)
                 or (self.model if provider == self.provider else None)
                 or _default_model(provider, self.task))
        return {"provider": provider, "model": model,
                "key": exp["key"].get(provider, _default_key(provider)) if provider != self.provider
                else self.api_key,
                "base": (exp["base"].get(provider)
                         or (self.base_url if provider == self.provider else None)
                         or _default_base_url(provider))}

    @property
    def available(self) -> bool:
        if not self.enabled:
            return False
        for prov in self.chain:
            if prov == "ollama" or _default_key(prov):
                return True
        return bool(self.api_key)

    def _max_tokens(self) -> int:
        """Cap generation length (= wall time) for OpenAI-style chat providers.

        Groq/xAI/OpenRouter apply no continuation cap by default; an uncapped
        model can ramble for 45s+. num_predict (per task) sets the ceiling,
        clamped to what every endpoint accepts.
        """
        try:
            n = int(self.options.get("num_predict", 1024))
        except (TypeError, ValueError):
            n = 1024
        return max(64, min(n, 3500))

    def _chat_payload(self, provider: str, model: str, prompt: str) -> dict:
        """OpenAI-compatible body. Caps tokens and trims reasoning on gpt-oss.

        gpt-oss models spend hidden "reasoning" tokens against max_tokens; on
        short caps that starves the visible answer (empty content / parse 400),
        so we request low reasoning effort there. Overridable per run.
        """
        payload = {"model": model,
                   "messages": [{"role": "user", "content": prompt}],
                   "temperature": self.temperature,
                   "max_tokens": self._max_tokens()}
        if provider == "groq" and "gpt-oss" in (model or ""):
            payload["reasoning_effort"] = self.options.get("reasoning_effort", "low")
        return payload

    def invoke(self, prompt: str) -> str:
        import httpx

        t0 = _time.perf_counter()
        deadline = t0 + self.budget

        def record(provider: str, model: str, mode: str, detail: str = "") -> None:
            _log_call({"node": self.task, "provider": provider,
                       "model": model, "temperature": self.temperature,
                       "latency_ms": int((_time.perf_counter() - t0) * 1000),
                       "mode": mode, "detail": detail[:200]})

        if not self.enabled:
            record(self.provider, self.model, "disabled", "CAREERPILOT_LLM=0")
            raise LLMError("LLM disabled via CAREERPILOT_LLM=0 — deterministic fallback.")
        if not prompt or not prompt.strip():
            record(self.provider, self.model, "error", "Empty prompt.")
            raise LLMError("Empty prompt.")
        primary = self.chain[0] if self.chain else self.provider
        ckey = _cache_key(self.task, self.temperature, primary, prompt)
        cached = _cache_get(ckey)
        if cached is not None:
            record(self.provider, self.model, "cache", "identical prompt")
            return cached

        last_err: Exception | None = None
        for prov in self.chain:
            remaining = deadline - _time.perf_counter()
            if remaining < 3:
                break
            cooling = _cooling(prov)
            if cooling > 0:
                record(prov, self._spec(prov)["model"], "skip",
                       f"cooling down {int(cooling)}s after failures")
                continue
            spec = self._spec(prov)
            if prov != "ollama" and not spec["key"]:
                record(prov, spec["model"], "error", "API key missing — trying next.")
                last_err = LLMError(f"{prov} API key missing.")
                continue
            cap = self.timeout if prov == "ollama" else min(
                self.timeout, REMOTE_TASK_TIMEOUTS.get(self.task, 30))
            attempt_to = min(PROVIDER_TIMEOUTS.get(prov, 40), remaining, cap)
            try:
                out = self._call_once(prov, spec, prompt, httpx, attempt_to)
                _mark_success(prov)
                _cache_put(ckey, out)
                record(prov, spec["model"], "live")
                return out
            except LLMError as exc:
                _mark_failure(prov, primary, exc)
                record(prov, spec["model"], "error", f"{exc} — trying next.")
                last_err = exc
            except Exception as exc:  # network/shape errors -> uniform type
                _mark_failure(prov, primary, exc)
                record(prov, spec["model"], "error", f"{exc} — trying next.")
                last_err = LLMError(f"{prov} call failed: {exc}")
        raise last_err or LLMError("LLM chain exhausted — deterministic fallback.")

    def _call_once(self, provider: str, spec: dict, prompt: str, httpx, timeout: float) -> str:
        if provider == "ollama":
            return self._ollama(prompt, httpx, spec["model"], spec["base"], timeout)
        if provider == "gemini":
            return self._gemini(prompt, httpx, spec["model"], spec["key"], timeout)
        if provider == "groq":
            return self._groq(prompt, httpx, spec["model"], spec["key"], timeout)
        if provider == "xai":
            return self._xai(prompt, httpx, spec["model"], spec["key"], timeout)
        if provider == "openrouter":
            return self._openrouter(prompt, httpx, spec["model"], spec["key"], timeout)
        if provider == "nvidia":
            return self._nvidia(prompt, httpx, spec["model"], spec["key"], timeout)
        raise LLMError(f"Unknown provider: {provider}")

    async def ainvoke(self, prompt: str) -> str:
        import httpx

        t0 = _time.perf_counter()
        deadline = t0 + self.budget

        def record(provider: str, model: str, mode: str, detail: str = "") -> None:
            _log_call({"node": self.task, "provider": provider,
                       "model": model, "temperature": self.temperature,
                       "latency_ms": int((_time.perf_counter() - t0) * 1000),
                       "mode": mode, "detail": detail[:200]})

        if not self.enabled:
            record(self.provider, self.model, "disabled", "CAREERPILOT_LLM=0")
            raise LLMError("LLM disabled via CAREERPILOT_LLM=0 — deterministic fallback.")
        if not prompt or not prompt.strip():
            record(self.provider, self.model, "error", "Empty prompt.")
            raise LLMError("Empty prompt.")
        primary = self.chain[0] if self.chain else self.provider
        ckey = _cache_key(self.task, self.temperature, primary, prompt)
        cached = _cache_get(ckey)
        if cached is not None:
            record(self.provider, self.model, "cache", "identical prompt")
            return cached

        last_err: Exception | None = None
        for prov in self.chain:
            remaining = deadline - _time.perf_counter()
            if remaining < 3:
                break
            cooling = _cooling(prov)
            if cooling > 0:
                record(prov, self._spec(prov)["model"], "skip",
                       f"cooling down {int(cooling)}s after failures")
                continue
            spec = self._spec(prov)
            if prov != "ollama" and not spec["key"]:
                record(prov, spec["model"], "error", "API key missing — trying next.")
                last_err = LLMError(f"{prov} API key missing.")
                continue
            cap = self.timeout if prov == "ollama" else min(
                self.timeout, REMOTE_TASK_TIMEOUTS.get(self.task, 30))
            attempt_to = min(PROVIDER_TIMEOUTS.get(prov, 40), remaining, cap)
            try:
                async with httpx.AsyncClient(timeout=attempt_to) as c:
                    out = await self._acall_once(prov, spec, prompt, c)
                _mark_success(prov)
                _cache_put(ckey, out)
                record(prov, spec["model"], "live")
                return out
            except LLMError as exc:
                _mark_failure(prov, primary, exc)
                record(prov, spec["model"], "error", f"{exc} — trying next.")
                last_err = exc
            except Exception as exc:
                _mark_failure(prov, primary, exc)
                record(prov, spec["model"], "error", f"{exc} — trying next.")
                last_err = LLMError(f"{prov} call failed: {exc}")
        raise last_err or LLMError("LLM chain exhausted — deterministic fallback.")

    async def _acall_once(self, provider: str, spec: dict, prompt: str, c) -> str:
        if provider == "ollama":
            r = await c.post(
                f"{spec['base']}/api/generate",
                json={"model": spec["model"], "prompt": prompt,
                      "stream": False, "keep_alive": "30m",
                      "options": {"temperature": self.temperature, **self.options}},
            )
            return _http_text(r, "ollama")
        if provider == "gemini":
            if not spec["key"]:
                raise LLMError("GEMINI_API_KEY is missing.")
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{spec['model']}:generateContent?key={spec['key']}")
            r = await c.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": self.temperature}})
            return _gemini_text(r)
        if provider in {"groq", "xai", "openrouter", "nvidia"}:
            endpoint, headers = _chat_endpoint(provider, spec["key"])
            payload = self._chat_payload(provider, spec["model"], prompt)
            r = await c.post(endpoint, headers=headers, json=payload)
            return _chat_text(r, provider)
        raise LLMError(f"Unknown provider: {provider}")

    # ---- sync provider calls ----
    def _ollama(self, prompt, httpx, model=None, base=None, timeout=None) -> str:
        opts = {"temperature": self.temperature, **self.options}
        with httpx.Client(timeout=timeout or self.timeout) as c:
            r = c.post(f"{base or self.base_url}/api/generate",
                       json={"model": model or self.model, "prompt": prompt,
                             "stream": False,
                             "keep_alive": "30m",  # stay loaded between agent calls
                             "options": opts})
            return _http_text(r, "ollama")

    def _gemini(self, prompt, httpx, model=None, key=None, timeout=None) -> str:
        key = key if key is not None else self.api_key
        if not key:
            raise LLMError("GEMINI_API_KEY is missing — paste it into .env later; using fallback.")
        with httpx.Client(timeout=timeout or self.timeout) as c:
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{model or self.model}:generateContent?key={key}")
            r = c.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": self.temperature}})
            return _gemini_text(r)

    def _chat(self, provider: str, prompt, httpx, model=None, key=None, timeout=None) -> str:
        key = key if key is not None else self.api_key
        if not key:
            raise LLMError(f"{provider.upper()}_API_KEY is missing — paste it into .env later.")
        endpoint, headers = _chat_endpoint(provider, key)
        payload = self._chat_payload(provider, model or self.model, prompt)
        with httpx.Client(timeout=timeout or self.timeout) as c:
            r = c.post(endpoint, headers=headers, json=payload)
            return _chat_text(r, provider)

    def _groq(self, prompt, httpx, model=None, key=None, timeout=None) -> str:
        return self._chat("groq", prompt, httpx, model, key, timeout)

    def _xai(self, prompt, httpx, model=None, key=None, timeout=None) -> str:
        return self._chat("xai", prompt, httpx, model, key, timeout)

    def _openrouter(self, prompt, httpx, model=None, key=None, timeout=None) -> str:
        return self._chat("openrouter", prompt, httpx, model, key, timeout)

    def _nvidia(self, prompt, httpx, model=None, key=None, timeout=None) -> str:
        return self._chat("nvidia", prompt, httpx, model, key, timeout)


def _chat_endpoint(provider: str, key: str) -> tuple[str, dict]:
    """OpenAI-compatible endpoint + headers per provider."""
    auth = {"Authorization": f"Bearer {key}"}
    if provider == "groq":
        return "https://api.groq.com/openai/v1/chat/completions", auth
    if provider == "xai":
        return "https://api.x.ai/v1/chat/completions", auth
    if provider == "openrouter":
        headers = {**auth, "Content-Type": "application/json"}
        if _env("OPENROUTER_REFERER", ""):
            headers["HTTP-Referer"] = _env("OPENROUTER_REFERER")
        if _env("OPENROUTER_TITLE", ""):
            headers["X-Title"] = _env("OPENROUTER_TITLE")
        return "https://openrouter.ai/api/v1/chat/completions", headers
    if provider == "nvidia":
        base = _env("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
        return f"{base}/chat/completions", auth
    raise LLMError(f"Unknown chat provider: {provider}")


def _http_text(r, provider: str) -> str:
    if r.status_code >= 400:
        raise LLMError(f"{provider} HTTP {r.status_code}: {r.text[:300]}")
    try:
        data = r.json()
    except Exception as exc:
        raise LLMError(f"{provider} non-JSON response: {exc}") from exc
    text = data.get("response", "")
    if not text.strip():
        raise LLMError(f"{provider} empty response (model={data.get('model', '?')}).")
    return text.strip()


def _gemini_text(r) -> str:
    if r.status_code >= 400:
        raise LLMError(f"gemini HTTP {r.status_code}: {r.text[:300]}")
    try:
        data = r.json()
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
    except Exception as exc:
        raise LLMError(f"gemini bad shape: {exc} :: {r.text[:300]}") from exc
    if not text:
        raise LLMError("gemini empty response.")
    return text


def _chat_text(r, provider: str) -> str:
    if r.status_code >= 400:
        raise LLMError(f"{provider} HTTP {r.status_code}: {r.text[:300]}")
    try:
        text = r.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        raise LLMError(f"{provider} bad shape: {exc}") from exc
    if not text:
        raise LLMError(f"{provider} empty response.")
    return text


def _default_model(provider: str, task: str | None = None) -> str:
    env_name = {
        "ollama": "OLLAMA_MODEL", "gemini": "GEMINI_MODEL",
        "groq": "GROQ_MODEL", "xai": "XAI_MODEL",
        "openrouter": "OPENROUTER_MODEL", "nvidia": "NVIDIA_MODEL",
    }.get(provider, "")
    fallback = {
        "ollama": "llama3.2", "gemini": "gemini-2.0-flash",
        "groq": "openai/gpt-oss-20b", "xai": "grok-beta",
        "openrouter": "openai/gpt-4o", "nvidia": "meta/llama-3.3-70b-instruct",
    }.get(provider, "llama3.2")
    if task and TASK_TIER.get(task) == "fast":
        fast = _env(f"{provider.upper()}_MODEL_FAST", "")
        if fast:
            return fast
    return _env(env_name, fallback) if env_name else fallback


def _default_base_url(provider: str) -> str:
    if provider == "ollama":
        return _env("OLLAMA_URL", "http://localhost:11434")
    return ""


def _default_key(provider: str) -> str:
    if provider == "gemini":
        return _env("GEMINI_API_KEY", "")
    if provider == "groq":
        return _env("GROQ_API_KEY", "")
    if provider == "xai":
        return _env("GROK_API_KEY", "") or _env("XAI_API_KEY", "")
    if provider == "openrouter":
        return _env("OPENROUTER_API_KEY", "")
    if provider == "nvidia":
        return _env("NVIDIA_API_KEY", "")
    return ""


def _primary() -> str:
    p = _env("LLM_PRIMARY", "").lower()
    if p in {"gemini", "ollama", "groq", "grok", "xai", "openrouter", "nvidia"}:
        return "xai" if p in {"grok", "xai"} else p
    # Auto: online key wins (prod), else local Ollama (dev/offline).
    if _env("OPENROUTER_API_KEY", ""):
        return "openrouter"
    if _env("GEMINI_API_KEY", ""):
        return "gemini"
    if _env("GROQ_API_KEY", ""):
        return "groq"
    if _env("GROK_API_KEY", "") or _env("XAI_API_KEY", ""):
        return "xai"
    if _env("NVIDIA_API_KEY", ""):
        return "nvidia"
    return "ollama"


def _task_provider(task: str) -> str | None:
    """Per-agent provider override from LLM_TASK_PROVIDERS.

    Format: "interview=nvidia,optimize=groq". The named provider is tried
    first for that task; the normal LLM_PRIMARY/LLM_FALLBACKS chain still
    covers it if that provider is down or has no key.
    """
    raw = _env("LLM_TASK_PROVIDERS", "")
    if not raw:
        return None
    for pair in raw.split(","):
        name, _, prov = pair.partition("=")
        if name.strip().lower() != (task or "").strip().lower():
            continue
        prov = _norm_provider(prov)
        return prov if prov in PROVIDERS else None
    return None


def get_llm(task: str = "explain", temperature: float | None = None,
            timeout: float | None = None) -> LLM:
    """Return an LLM for a task. Temps frozen per agents.md matrix.

    CAREERPILOT_LLM=0 disables all LLM calls (tests/CI/offline) — every
    agent falls back to its deterministic template and logs to errors.
    """
    provider = _task_provider(task) or _primary()
    temp = TASK_TEMPS.get(task, 0.2) if temperature is None else temperature
    to = TASK_TIMEOUTS.get(task, 90) if timeout is None else timeout
    llm = LLM(model=provider, temperature=temp, task=task, timeout=to,
              options={**BASE_OPTIONS, **TASK_PARAMS.get(task, {})})
    if _env("CAREERPILOT_LLM", "1") == "0":
        llm.enabled = False
    return llm


def parse_json_block(text: str) -> dict | list:
    """Extract the first {...} or [...] JSON block from LLM output.

    Uses raw_decode so trailing commentary after valid JSON never breaks
    parsing (the #1 small-model failure mode).
    """
    from json import JSONDecoder

    text = text.strip()
    # Strip markdown fences small models love to add.
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start_c, start_s = text.find("{"), text.find("[")
    starts = [s for s in (start_c, start_s) if s != -1]
    if not starts:
        raise ValueError("No JSON found in LLM output.")
    start = min(starts)
    try:
        value, _ = JSONDecoder().raw_decode(text[start:])
        return value
    except Exception:
        pass
    end = text.rfind("}" if text[start] == "{" else "]") + 1
    return json.loads(text[start:end])


def llm_json(task: str, prompt: str, retries: int = 1) -> tuple[dict | list, list[dict]]:
    """Invoke the task LLM and parse JSON, with one repair retry.

    Returns (parsed, errors). The repair retry shows the model its bad
    output and demands bare JSON — this rescues most small-model shape
    failures without a full fallback. Raises LLMError if all attempts fail.
    """
    errors: list[dict] = []
    llm = get_llm(task)
    if not llm.available:
        raise LLMError("No LLM key — deterministic fallback.")
    attempt = llm.invoke(prompt)
    try:
        return parse_json_block(attempt), errors
    except Exception as first_exc:
        errors.append({"node": task, "message": f"JSON parse failed, repairing: {first_exc}"})
    if retries > 0:
        repair = (
            "Your previous output was NOT valid JSON. Return ONLY the JSON value "
            "— no markdown fences, no commentary, no trailing text. The exact same "
            "content, fixed:\n" + attempt[:6000]
        )
        try:
            return parse_json_block(llm.invoke(repair)), errors
        except Exception as repair_exc:
            errors.append({"node": task, "message": f"Repair failed: {repair_exc}"})
            raise LLMError(f"LLM JSON unparseable: {repair_exc}") from repair_exc
    raise LLMError("LLM JSON unparseable.")

"""Ollama tuning tests: per-task params + custom Modelfile (offline)."""
from pathlib import Path

from app.core import llm as core


def test_task_params_shape():
    for task, params in core.TASK_PARAMS.items():
        assert params["num_predict"] > 0 and params["num_ctx"] >= 4096, task
    assert core.TASK_PARAMS["interview"]["num_predict"] >= 2000
    assert core.TASK_TIMEOUTS["interview"] >= 240


def test_get_llm_carries_options_and_timeout():
    llm = core.get_llm("interview")
    assert llm.options["num_predict"] == core.TASK_PARAMS["interview"]["num_predict"]
    assert llm.options["top_p"] == 0.9
    assert llm.timeout == core.TASK_TIMEOUTS["interview"]
    assert core.get_llm("explain").options["num_predict"] < llm.options["num_predict"]


def test_modelfile_bakes_persona_and_params():
    mf = Path(__file__).resolve().parents[1] / "ollama" / "Modelfile"
    text = mf.read_text(encoding="utf-8")
    assert "FROM llama3.2" in text
    assert "SYSTEM" in text and "PLAIN TEXT ONLY" in text
    assert "never invent" in text.lower() or "NEVER invent" in text
    for param in ("temperature", "top_p", "repeat_penalty", "num_ctx"):
        assert param in text

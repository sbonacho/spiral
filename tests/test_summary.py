import json

import pytest

from conftest import make_cfg
from spiral import summary
from spiral.errors import SpiralError

GOOD = {"titulo": "t", "resumen_corto": "c", "resumen_largo": "l", "capitulos": [], "tags": [],
        "hilo_x": ["x"], "post_blog_md": "p", "clips": []}
SEGS = [{"start": 0, "end": 1, "text": "hola"}]


def fake_provider(monkeypatch, name, reply, seen=None):
    mod = summary.PROVIDERS[name]
    monkeypatch.setattr(mod, "check", lambda cfg: None)

    def complete(cfg, prompt):
        if seen is not None:
            seen.append(prompt)
        return reply
    monkeypatch.setattr(mod, "complete", complete)


def test_invalid_response_names_missing_field(work, monkeypatch):
    bad = {k: v for k, v in GOOD.items() if k != "clips"}
    fake_provider(monkeypatch, "claude", json.dumps(bad))
    with pytest.raises(SpiralError, match="clips"):
        summary.summarize(make_cfg(work), SEGS, lambda m: None)


def test_not_json_is_an_error(work, monkeypatch):
    fake_provider(monkeypatch, "claude", "no es json")
    with pytest.raises(SpiralError, match="JSON"):
        summary.summarize(make_cfg(work), SEGS, lambda m: None)


def test_text_around_json_is_tolerated_and_offset_added(work, monkeypatch):
    fake_provider(monkeypatch, "claude", "claro:\n" + json.dumps(GOOD) + "\nfin")
    assert summary.summarize(make_cfg(work), SEGS, lambda m: None, 12)["offset_intro"] == 12


def test_unknown_provider_lists_valid_ones(work):
    with pytest.raises(SpiralError, match="claude, gemini, ollama"):
        summary.summarize(make_cfg(work, LLM_PROVIDER="otro"), SEGS, lambda m: None)


def test_gemini_without_key_stops_before_calling(work, monkeypatch):
    called = []
    monkeypatch.setattr(summary.gemini, "complete", lambda *a: called.append(1))
    with pytest.raises(SpiralError, match="GEMINI_API_KEY"):
        summary.summarize(make_cfg(work, LLM_PROVIDER="gemini"), SEGS, lambda m: None)
    assert not called


def test_ollama_needs_model(work):
    with pytest.raises(SpiralError, match="OLLAMA_MODEL"):
        summary.summarize(make_cfg(work, LLM_PROVIDER="ollama"), SEGS, lambda m: None)


def test_language_in_prompt_and_provider_announced(work, monkeypatch):
    seen, logs = [], []
    fake_provider(monkeypatch, "gemini", json.dumps(GOOD), seen)
    summary.summarize(make_cfg(work, LLM_PROVIDER="gemini", PODCAST_LANGUAGE="en"), SEGS, logs.append)
    assert 'code\n"en"' in seen[0] or '"en"' in seen[0]
    assert any("gemini" in m for m in logs)

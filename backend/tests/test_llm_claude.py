"""brain._complete with ANTHROPIC_API_KEY set: Claude through the Anthropic SDK (a stand-in client, no network)."""
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app import brain


def reply(text, stop="end_turn"):
    return SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=text)])


@pytest.fixture
def claude(monkeypatch):
    """Records each request. Set claude.beta_error to make the fallback-enabled call fail with a 400."""
    calls = SimpleNamespace(beta=[], plain=[], beta_error=False, answer=reply('{"text": "ok"}'))

    def beta_create(**kw):
        calls.beta.append(kw)
        if calls.beta_error:
            raise anthropic.BadRequestError("no", response=httpx.Response(400, request=httpx.Request("POST", "https://x")), body=None)
        return calls.answer

    def plain_create(**kw):
        calls.plain.append(kw)
        return calls.answer

    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=beta_create)),
                           messages=SimpleNamespace(create=plain_create))
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    return calls


def test_claude_gets_the_schema_effort_and_fallbacks(claude):
    assert brain._complete("prompt", brain.COACH_SCHEMA, effort="low") == '{"text": "ok"}'
    sent = claude.beta[0]
    assert sent["model"] == "claude-opus-5-5" and sent["fallbacks"] == "default"
    assert sent["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": brain.COACH_SCHEMA}}


def test_plain_request_when_fallbacks_are_refused(claude):
    claude.beta_error = True
    assert brain._complete("prompt") == '{"text": "ok"}'
    assert "fallbacks" not in claude.plain[0] and claude.plain[0]["output_config"]["effort"] == "medium"


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_no_usable_reply_is_llm_unavailable(claude, stop):
    claude.answer = reply("", stop)
    with pytest.raises(brain.LLMUnavailable):
        brain._complete("prompt")

import json
from unittest import mock

import pytest

from ai_search import backends


def test_get_backend_default_is_anthropic(settings):
    settings.BPP_AI_BACKEND = "anthropic"
    assert isinstance(backends.get_backend(), backends.AnthropicBackend)


def test_get_backend_openai(settings):
    settings.BPP_AI_BACKEND = "openai"
    assert isinstance(backends.get_backend(), backends.OpenAICompatibleBackend)


def test_get_backend_unknown_falls_back_to_anthropic(settings):
    settings.BPP_AI_BACKEND = "cos-nieznanego"
    assert isinstance(backends.get_backend(), backends.AnthropicBackend)


def _system_blocks():
    return [{"type": "text", "text": "REGULY", "cache_control": {"type": "ephemeral"}}]


def test_anthropic_backend_call_maps_usage_and_stop_reason(settings):
    settings.BPP_AI_MODEL = "claude-sonnet-5"
    settings.BPP_AI_LLM_TIMEOUT = 30
    parsed = backends.DSLQuery(query="rok = 2024", error=None)
    fake_resp = mock.Mock()
    fake_resp.parsed_output = parsed
    fake_resp.stop_reason = "end_turn"
    fake_resp.usage = mock.Mock(
        input_tokens=100,
        output_tokens=20,
        cache_read_input_tokens=5,
        cache_creation_input_tokens=7,
    )
    fake_client = mock.Mock()
    fake_client.messages.parse.return_value = fake_resp
    with mock.patch("anthropic.Anthropic", return_value=fake_client) as ctor:
        result = backends.AnthropicBackend().call(
            _system_blocks(), [{"role": "user", "content": "pytanie"}]
        )
    ctor.assert_called_once_with(timeout=30)
    assert result.parsed is parsed
    assert result.stop_reason == "end_turn"
    assert result.usage == {
        "input_tokens": 100,
        "output_tokens": 20,
        "cache_read_tokens": 5,
        "cache_write_tokens": 7,
    }
    call_kwargs = fake_client.messages.parse.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-5"
    assert call_kwargs["thinking"] == {"type": "disabled"}
    assert call_kwargs["max_tokens"] == 500
    assert call_kwargs["output_format"] is backends.DSLQuery


def _fake_openai_response(content: str, finish_reason="stop"):
    resp = mock.Mock()
    choice = mock.Mock()
    choice.message.content = content
    choice.finish_reason = finish_reason
    resp.choices = [choice]
    resp.usage = mock.Mock(prompt_tokens=50, completion_tokens=10)
    return resp


def test_openai_backend_call_parses_valid_json(settings):
    settings.BPP_AI_BACKEND = "openai"
    settings.BPP_AI_MODEL = "qwen3:8b"
    settings.BPP_AI_BASE_URL = "http://localhost:11434/v1"
    settings.BPP_AI_API_KEY = ""
    settings.BPP_AI_LLM_TIMEOUT = 30

    fake_resp = _fake_openai_response(
        json.dumps({"query": "rok = 2024", "error": None})
    )
    fake_client = mock.Mock()
    fake_client.chat.completions.create.return_value = fake_resp

    with mock.patch("openai.OpenAI", return_value=fake_client) as ctor:
        result = backends.OpenAICompatibleBackend().call(
            _system_blocks(), [{"role": "user", "content": "publikacje z 2024"}]
        )

    ctor.assert_called_once_with(
        base_url="http://localhost:11434/v1", api_key="sk-noauth", timeout=30
    )
    assert result.parsed.query == "rok = 2024"
    assert result.parsed.error is None
    assert result.stop_reason == "stop"
    assert result.usage == {
        "input_tokens": 50,
        "output_tokens": 10,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
    }
    create_kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert create_kwargs["model"] == "qwen3:8b"
    assert create_kwargs["temperature"] == 0
    assert create_kwargs["messages"][0] == {"role": "system", "content": "REGULY"}
    assert create_kwargs["messages"][1] == {
        "role": "user",
        "content": "publikacje z 2024",
    }
    assert create_kwargs["response_format"]["json_schema"]["strict"] is True


def test_openai_backend_call_flattens_multiple_system_blocks(settings):
    settings.BPP_AI_BACKEND = "openai"
    settings.BPP_AI_BASE_URL = "http://localhost:11434/v1"
    settings.BPP_AI_API_KEY = ""
    system = [
        {"type": "text", "text": "CZESC1"},
        {"type": "text", "text": "CZESC2", "cache_control": {"type": "ephemeral"}},
    ]
    fake_resp = _fake_openai_response(
        json.dumps({"query": "rok = 2024", "error": None})
    )
    fake_client = mock.Mock()
    fake_client.chat.completions.create.return_value = fake_resp

    with mock.patch("openai.OpenAI", return_value=fake_client):
        backends.OpenAICompatibleBackend().call(
            system, [{"role": "user", "content": "x"}]
        )

    create_kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert create_kwargs["messages"][0]["content"] == "CZESC1\nCZESC2"


def test_openai_backend_uses_api_key_when_set(settings):
    settings.BPP_AI_BACKEND = "openai"
    settings.BPP_AI_BASE_URL = "http://localhost:8000/v1"
    settings.BPP_AI_API_KEY = "sk-real-key"
    fake_resp = _fake_openai_response(
        json.dumps({"query": "rok = 2024", "error": None})
    )
    fake_client = mock.Mock()
    fake_client.chat.completions.create.return_value = fake_resp

    with mock.patch("openai.OpenAI", return_value=fake_client) as ctor:
        backends.OpenAICompatibleBackend().call(
            _system_blocks(), [{"role": "user", "content": "x"}]
        )

    assert ctor.call_args.kwargs["api_key"] == "sk-real-key"


@pytest.mark.parametrize("bad_content", ["nie-json", "{niepoprawny json", "[]"])
def test_openai_backend_call_invalid_json_returns_meaningful_error(
    settings, bad_content
):
    settings.BPP_AI_BACKEND = "openai"
    settings.BPP_AI_BASE_URL = "http://localhost:11434/v1"
    settings.BPP_AI_API_KEY = ""
    fake_resp = _fake_openai_response(bad_content)
    fake_client = mock.Mock()
    fake_client.chat.completions.create.return_value = fake_resp

    with mock.patch("openai.OpenAI", return_value=fake_client):
        result = backends.OpenAICompatibleBackend().call(
            _system_blocks(), [{"role": "user", "content": "x"}]
        )

    assert result.parsed.query is None
    assert "niepoprawny JSON" in result.parsed.error

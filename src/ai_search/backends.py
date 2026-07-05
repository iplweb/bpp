"""Backendy LLM dla tłumacza pytań PL -> DjangoQL.

Dwa backendy za wspólnym kontraktem ``call(system, messages) -> LLMResult``:

- ``AnthropicBackend`` — natywny SDK ``anthropic``, ``messages.parse`` ze
  structured output (``DSLQuery``), prompt caching (bloki ``system`` z
  ``cache_control``), thinking wyłączony. Domyślny, płatny.
- ``OpenAICompatibleBackend`` — SDK ``openai`` wskazany na dowolny lokalny
  serwer zgodny z OpenAI Chat Completions API (Ollama, llama.cpp/llama-server,
  vLLM, LM Studio, LocalAI). Spłaszcza bloki ``system`` do zwykłego stringa
  (lokalne serwery nie znają ``cache_control``) i prosi o JSON zgodny ze
  schematem ``DSLQuery`` przez ``response_format={"type": "json_schema", ...}``.

``system`` w obu przypadkach to lista bloków anthropic
(``[{"type": "text", "text": ..., "cache_control": {...}}]``), a ``messages``
to ``[{"role": "user", "content": str}]`` — kontrakt ustalony przez
dotychczasowe wywołanie w ``translator.py``.
"""

import json
import logging
from dataclasses import dataclass, field

import anthropic
from django.conf import settings
from pydantic import BaseModel, ConfigDict, ValidationError

logger = logging.getLogger(__name__)


class DSLQuery(BaseModel):
    """Ustrukturyzowana odpowiedź modelu (``output_format`` / JSON schema)."""

    model_config = ConfigDict(extra="forbid")
    query: str | None
    error: str | None


@dataclass
class LLMResult:
    """Znormalizowany wynik wywołania modelu, niezależny od backendu."""

    parsed: DSLQuery
    usage: dict = field(default_factory=dict)
    stop_reason: str | None = None


class AnthropicBackend:
    """Natywny SDK ``anthropic`` — structured output, prompt caching."""

    def _client(self) -> anthropic.Anthropic:
        return anthropic.Anthropic(timeout=settings.BPP_AI_LLM_TIMEOUT)

    def _extract_usage(self, resp) -> dict:
        u = resp.usage
        return {
            "input_tokens": getattr(u, "input_tokens", 0) or 0,
            "output_tokens": getattr(u, "output_tokens", 0) or 0,
            "cache_read_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
            "cache_write_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        }

    def call(self, system, messages) -> LLMResult:
        resp = self._client().messages.parse(
            model=settings.BPP_AI_MODEL,
            max_tokens=500,
            thinking={"type": "disabled"},
            system=system,
            messages=messages,
            output_format=DSLQuery,
        )
        return LLMResult(
            parsed=resp.parsed_output,
            usage=self._extract_usage(resp),
            stop_reason=getattr(resp, "stop_reason", None),
        )


class OpenAICompatibleBackend:
    """Dowolny lokalny serwer zgodny z OpenAI Chat Completions API."""

    def _client(self):
        from openai import OpenAI

        return OpenAI(
            base_url=settings.BPP_AI_BASE_URL,
            api_key=settings.BPP_AI_API_KEY or "sk-noauth",
            timeout=settings.BPP_AI_LLM_TIMEOUT,
        )

    @staticmethod
    def _flatten_system(system) -> str:
        return "\n".join(block["text"] for block in system)

    def call(self, system, messages) -> LLMResult:
        system_text = self._flatten_system(system)
        user_content = messages[-1]["content"]
        resp = self._client().chat.completions.create(
            model=settings.BPP_AI_MODEL,
            max_tokens=500,
            temperature=0,
            messages=[
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_content},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "dsl_query",
                    "schema": DSLQuery.model_json_schema(),
                    "strict": True,
                },
            },
        )
        choice = resp.choices[0]
        raw = choice.message.content
        try:
            data = json.loads(raw)
            parsed = DSLQuery(**data)
        except (json.JSONDecodeError, TypeError, ValidationError):
            logger.warning("Model lokalny zwrócił niepoprawny JSON: %r", raw)
            parsed = DSLQuery(
                query=None, error="Model lokalny zwrócił niepoprawny JSON."
            )
        usage = resp.usage
        return LLMResult(
            parsed=parsed,
            usage={
                "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
            },
            stop_reason=choice.finish_reason,
        )


def get_backend():
    """Wybiera backend wg ``settings.BPP_AI_BACKEND`` (domyślnie anthropic)."""
    if settings.BPP_AI_BACKEND == "openai":
        return OpenAICompatibleBackend()
    return AnthropicBackend()

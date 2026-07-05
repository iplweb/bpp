"""Tłumacz pytań w języku polskim na zapytania DjangoQL (LLM + walidacja).

Wywołuje model (SDK ``anthropic``, ``messages.parse`` z ustrukturyzowanym
``output_format=DSLQuery``), waliduje zwrócone zapytanie realnym parserem
DjangoQL (``apply_search`` + ``BppQLSchema``) i — jeśli składnia jest zła —
ponawia próbę, przekazując modelowi dokładny komunikat błędu (linia/kolumna),
do ``settings.BPP_AI_MAX_RETRIES`` razy.
"""

import logging
from dataclasses import dataclass, field

import anthropic
from django.conf import settings
from django.core.exceptions import FieldError, ValidationError
from djangoql.exceptions import DjangoQLError
from djangoql.queryset import apply_search
from pydantic import BaseModel, ConfigDict

from ai_search import prompts, schema_export
from bpp.djangoql_helpers import _error_location, _format_error_text
from bpp.djangoql_schema import BppQLSchema
from bpp.views.zapytanie import MODELS

logger = logging.getLogger(__name__)


class DSLQuery(BaseModel):
    """Ustrukturyzowana odpowiedź modelu (``output_format``)."""

    model_config = ConfigDict(extra="forbid")
    query: str | None
    error: str | None


@dataclass
class TranslationResult:
    query: str | None = None
    error: str | None = None
    usage: dict = field(default_factory=dict)
    attempts: int = 0
    retried: bool = False
    budget_blocked: bool = False


def validate_query(query: str, model_key: str):
    """Zwraca ``(None, None)`` gdy zapytanie parsuje się poprawnie, inaczej
    ``(komunikat, {line, column, mark})``."""
    model = MODELS[model_key]
    try:
        apply_search(model.objects.all(), query, schema=BppQLSchema)
        return None, None
    except (DjangoQLError, FieldError, ValidationError, ValueError) as exc:
        line, column, mark = _error_location(exc, query)
        loc = {"line": line, "column": column, "mark": mark} if line else None
        return _format_error_text(exc), loc


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(timeout=settings.BPP_AI_LLM_TIMEOUT)


def _call_model(system, messages):
    """Pojedyncze wywołanie modelu (wydzielone dla testowalności)."""
    return _client().messages.parse(
        model=settings.BPP_AI_MODEL,
        max_tokens=500,
        thinking={"type": "disabled"},
        system=system,
        messages=messages,
        output_format=DSLQuery,
    )


def _extract_usage(resp) -> dict:
    u = resp.usage
    return {
        "input_tokens": getattr(u, "input_tokens", 0) or 0,
        "output_tokens": getattr(u, "output_tokens", 0) or 0,
        "cache_read_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
        "cache_write_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
    }


def _accumulate(total: dict, part: dict):
    for k, v in part.items():
        total[k] = total.get(k, 0) + v


def translate(pytanie: str, model_key: str, budget_check=None) -> TranslationResult:
    """NL (polski) -> DjangoQL. Waliduje i, przy błędzie składni, zwraca do
    modelu konkretny komunikat DjangoQL (linia/kolumna) i ponawia — bounded.

    ``budget_check`` (opcjonalnie) to callable bez argumentów zwracający
    obiekt z atrybutami ``.ok``/``.reason`` (np. ``budget.check_budget``).
    Jest sprawdzany na POCZĄTKU każdej iteracji pętli — także przed każdym
    retry — żeby budżet wyczerpany W TRAKCIE bounded-retry przerwał dalsze
    (płatne) wywołania modelu."""
    system = prompts.build_system(schema_export.schema_for_llm(model_key), model_key)
    # cap 2 per spec (domyślnie 1, ale niezależnie od ustawienia max. 2 retry)
    max_retries = min(settings.BPP_AI_MAX_RETRIES, 2)
    total_usage: dict = {}
    result = TranslationResult()
    content = pytanie

    for attempt in range(max_retries + 1):
        if budget_check is not None:
            status = budget_check()
            if not status.ok:
                result.budget_blocked = True
                result.error = status.reason
                result.query = None
                return result

        result.attempts = attempt + 1
        resp = _call_model(system, [{"role": "user", "content": content}])
        _accumulate(total_usage, _extract_usage(resp))
        result.usage = total_usage

        if getattr(resp, "stop_reason", None) == "refusal":
            result.query = None
            result.error = "Model odmówił odpowiedzi na to pytanie."
            return result

        parsed = resp.parsed_output
        if parsed.query is None:
            result.query = None
            result.error = parsed.error or "Nie można wyrazić pytania w DSL."
            return result

        err, loc = validate_query(parsed.query, model_key)
        if err is None:
            result.query = parsed.query
            result.error = None
            return result

        # Błąd składni — przygotuj feedback do modelu i ponów (jeśli
        # został budżet prób).
        result.query = None
        result.error = err
        if attempt < max_retries:
            result.retried = True
            where = ""
            if loc and loc.get("line"):
                where = f" (linia {loc['line']}, kolumna {loc['column']})"
            content = (
                f"{pytanie}\n\nPoprzednie zapytanie `{parsed.query}` zwróciło "
                f"błąd DjangoQL: {err}{where}. Skoryguj i zwróć poprawne "
                f"zapytanie."
            )
    return result

import logging

from django.conf import settings
from django.core.cache import cache
from djangoql.llm import describe_schema_for_llm

from bpp.djangoql_schema import BppQLSchema
from bpp.views.zapytanie import MODELS

logger = logging.getLogger(__name__)


def _cache_key(model_key: str) -> str:
    return f"ai_search:schema:{model_key}"


def _build(model_key: str) -> str:
    """Zbuduj opis schematu dla danego klucza modelu (rekord/autor).

    Podnosi KeyError dla nieznanego klucza. describe_schema_for_llm sięga bazy
    dla pól z suggest_options — dlatego wynik jest cache'owany. Zwraca
    zwarty (compact), samodokumentujący się string, gotowy do wstrzyknięcia
    do promptu LLM."""
    model = MODELS[model_key]
    return describe_schema_for_llm(
        BppQLSchema(model),
        format="compact",
        max_fk_options=settings.BPP_AI_MAX_FK_OPTIONS,
    )


def regenerate(model_key: str) -> str:
    data = _build(model_key)
    cache.set(_cache_key(model_key), data, settings.BPP_AI_SCHEMA_CACHE_TTL)
    return data


def schema_for_llm(model_key: str) -> str:
    cached = cache.get(_cache_key(model_key))
    if cached is not None:
        return cached
    return regenerate(model_key)

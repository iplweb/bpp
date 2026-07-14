"""Wykrywanie stanu konfiguracji wyszukiwania AI.

Jedno źródło prawdy o tym, czy funkcja „szukaj przez AI" jest GOTOWA do
użycia (``BPP_AI_SEARCH_ENABLED`` + poświadczenia aktywnego backendu), czy
tylko dostępna jako ekran instrukcji konfiguracji. Używane przez:

- widok ``ZapytanieAIView`` — formularz (skonfigurowane) vs instrukcja
  (nieskonfigurowane),
- context processor ``ai_search_flags`` — pozycja menu + dopisek
  „(konfiguracja)".

Bez efektów ubocznych i tanie (czyta tylko ``settings`` + ``os.environ``),
więc bezpieczne do wołania per-request w context processorze.
"""

import os
from dataclasses import dataclass

from django.conf import settings

from ai_search.backends import active_backend_name


@dataclass(frozen=True)
class ConfigState:
    """Stan konfiguracji AI. ``configured`` == gotowe do użycia."""

    configured: bool
    enabled: bool
    backend: str
    reason: str = ""


def _anthropic_api_key() -> str:
    """Klucz API Anthropic. Pierwszeństwo ma ustawienie ``BPP_AI_API_KEY``,
    z fallbackiem do zmiennej środowiskowej ``ANTHROPIC_API_KEY`` (domyślne
    źródło klucza w SDK ``anthropic``). Pusty string == brak klucza."""
    return settings.BPP_AI_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")


def configuration_state() -> ConfigState:
    """Oblicz aktualny stan konfiguracji wyszukiwania AI."""
    backend = active_backend_name()
    enabled = bool(settings.BPP_AI_SEARCH_ENABLED)

    if not enabled:
        return ConfigState(
            configured=False,
            enabled=False,
            backend=backend,
            reason="Wyszukiwanie AI jest wyłączone "
            "(ustaw zmienną BPP_AI_SEARCH_ENABLED=1).",
        )

    if backend == "openai":
        if not settings.BPP_AI_BASE_URL:
            return ConfigState(
                configured=False,
                enabled=True,
                backend=backend,
                reason="Backend openai (model lokalny) wymaga adresu "
                "serwera — ustaw BPP_AI_BASE_URL "
                "(np. http://localhost:11434/v1).",
            )
    elif not _anthropic_api_key():
        return ConfigState(
            configured=False,
            enabled=True,
            backend=backend,
            reason="Backend anthropic wymaga klucza API — ustaw "
            "BPP_AI_API_KEY lub zmienną środowiskową ANTHROPIC_API_KEY.",
        )

    return ConfigState(configured=True, enabled=True, backend=backend)


def is_configured() -> bool:
    """Czy funkcja AI jest w pełni skonfigurowana (gotowa do użycia)."""
    return configuration_state().configured

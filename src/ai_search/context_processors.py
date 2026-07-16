from django.conf import settings

from ai_search.config import is_configured


def ai_search_flags(request):
    """Flagi AI dla szablonów (menu górne).

    - ``BPP_AI_SEARCH_ENABLED`` — surowa flaga funkcji (zachowana dla zgodności).
    - ``BPP_AI_SEARCH_CONFIGURED`` — czy funkcja jest GOTOWA do użycia (flaga +
      poświadczenia backendu). Gdy ``False``, pozycja menu prowadzi do ekranu
      instrukcji konfiguracji zamiast do formularza.
    """
    return {
        "BPP_AI_SEARCH_ENABLED": settings.BPP_AI_SEARCH_ENABLED,
        "BPP_AI_SEARCH_CONFIGURED": is_configured(),
    }

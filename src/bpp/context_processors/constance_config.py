"""
Context processor udostępniający ustawienia z django-constance dla szablonów.

Zapewnia fallback do Django settings (zmiennych środowiskowych) w przypadku,
gdy constance nie jest jeszcze skonfigurowane (np. podczas migracji).
"""

_CONSTANCE_KEYS = (
    "UZYWAJ_PUNKTACJI_WEWNETRZNEJ",
    "POKAZUJ_INDEX_COPERNICUS",
    "POKAZUJ_PUNKTACJA_SNIP",
    "POKAZUJ_OSWIADCZENIE_KEN",
    "SKROT_WYDZIALU_W_NAZWIE_JEDNOSTKI",
    "UCZELNIA_UZYWA_WYDZIALOW",
    "GOOGLE_ANALYTICS_PROPERTY_ID",
    "GOOGLE_VERIFICATION_CODE",
    "WYDRUK_MARGINES_GORA",
    "WYDRUK_MARGINES_DOL",
    "WYDRUK_MARGINES_LEWO",
    "WYDRUK_MARGINES_PRAWO",
)


def constance_config(request):
    """
    Udostępnia wybrane ustawienia z django-constance dla szablonów.

    Używa ``constance.utils.get_values_for_keys`` zamiast
    ``getattr(config, key)``. Powód: od constance 4.x
    ``Config.__getattr__`` wykrywa aktywną pętlę asyncio (a Django
    test client w nowszych wersjach startuje ją wewnętrznie) i
    zwraca ``AsyncValueProxy`` — stringifikacja takiego proxy w
    szablonie (``{{ VAR|default:"..." }}``) emituje
    ``RuntimeWarning: Synchronous access to Constance setting '...'
    inside an async loop``. ``get_values_for_keys`` idzie prosto do
    backendu, bez tej detekcji, więc działa identycznie w sync i
    async kontekście.

    Fallback: jeżeli constance nie jest skonfigurowane, używa wartości
    z Django settings (ze zmiennych środowiskowych).

    Returns:
        dict: Słownik z ustawieniami dostępnymi w szablonach
    """
    try:
        from constance.utils import get_values_for_keys

        return get_values_for_keys(_CONSTANCE_KEYS)
    except (ImportError, AttributeError):
        from django.conf import settings

        return {
            "UZYWAJ_PUNKTACJI_WEWNETRZNEJ": getattr(
                settings, "UZYWAJ_PUNKTACJI_WEWNETRZNEJ", True
            ),
            "POKAZUJ_INDEX_COPERNICUS": True,
            "POKAZUJ_PUNKTACJA_SNIP": True,
            "POKAZUJ_OSWIADCZENIE_KEN": getattr(
                settings, "BPP_POKAZUJ_OSWIADCZENIE_KEN", False
            ),
            "SKROT_WYDZIALU_W_NAZWIE_JEDNOSTKI": getattr(
                settings, "DJANGO_BPP_SKROT_WYDZIALU_W_NAZWIE_JEDNOSTKI", True
            ),
            "UCZELNIA_UZYWA_WYDZIALOW": getattr(
                settings, "DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW", True
            ),
            "GOOGLE_ANALYTICS_PROPERTY_ID": getattr(
                settings, "GOOGLE_ANALYTICS_PROPERTY_ID", None
            ),
            "GOOGLE_VERIFICATION_CODE": getattr(
                settings, "WEBMASTER_VERIFICATION", {}
            ).get("google", ""),
            "WYDRUK_MARGINES_GORA": "2cm",
            "WYDRUK_MARGINES_DOL": "2cm",
            "WYDRUK_MARGINES_LEWO": "2cm",
            "WYDRUK_MARGINES_PRAWO": "2cm",
        }

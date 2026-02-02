"""
Context processor udostępniający ustawienia z django-constance dla szablonów.

Zapewnia fallback do Django settings (zmiennych środowiskowych) w przypadku,
gdy constance nie jest jeszcze skonfigurowane (np. podczas migracji).
"""


def constance_config(request):
    """
    Udostępnia wybrane ustawienia z django-constance dla szablonów.

    Fallback: jeżeli constance nie jest skonfigurowane, używa wartości
    z Django settings (ze zmiennych środowiskowych).

    Returns:
        dict: Słownik z ustawieniami dostępnymi w szablonach
    """
    try:
        from constance import config

        return {
            "UZYWAJ_PUNKTACJI_WEWNETRZNEJ": config.UZYWAJ_PUNKTACJI_WEWNETRZNEJ,
            "POKAZUJ_INDEX_COPERNICUS": config.POKAZUJ_INDEX_COPERNICUS,
            "POKAZUJ_PUNKTACJA_SNIP": config.POKAZUJ_PUNKTACJA_SNIP,
            "POKAZUJ_OSWIADCZENIE_KEN": config.POKAZUJ_OSWIADCZENIE_KEN,
            "SKROT_WYDZIALU_W_NAZWIE_JEDNOSTKI": (
                config.SKROT_WYDZIALU_W_NAZWIE_JEDNOSTKI
            ),
            "UCZELNIA_UZYWA_WYDZIALOW": config.UCZELNIA_UZYWA_WYDZIALOW,
            "GOOGLE_ANALYTICS_PROPERTY_ID": config.GOOGLE_ANALYTICS_PROPERTY_ID,
            "GOOGLE_VERIFICATION_CODE": config.GOOGLE_VERIFICATION_CODE,
            "WYDRUK_MARGINES_GORA": config.WYDRUK_MARGINES_GORA,
            "WYDRUK_MARGINES_DOL": config.WYDRUK_MARGINES_DOL,
            "WYDRUK_MARGINES_LEWO": config.WYDRUK_MARGINES_LEWO,
            "WYDRUK_MARGINES_PRAWO": config.WYDRUK_MARGINES_PRAWO,
        }
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

"""
Context processor udostępniający ustawienia per-uczelnia dla szablonów.

Ustawienia przeniesione z django-constance do modelu Uczelnia.
Fallback do wartości domyślnych gdy brak uczelni w request.
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
    Udostępnia ustawienia per-uczelnia dla szablonów.

    Odczytuje wartości z obiektu Uczelnia powiązanego z bieżącym request
    (ustawionego przez SiteResolutionMiddleware).

    Returns:
        dict: Słownik z ustawieniami dostępnymi w szablonach
    """
    uczelnia = getattr(request, "_uczelnia", None)

    if uczelnia is not None:
        return {
            "UZYWAJ_PUNKTACJI_WEWNETRZNEJ": uczelnia.pokazuj_punktacje_wewnetrzna,
            "POKAZUJ_INDEX_COPERNICUS": uczelnia.pokazuj_index_copernicus,
            "POKAZUJ_PUNKTACJA_SNIP": uczelnia.pokazuj_punktacja_snip,
            "POKAZUJ_OSWIADCZENIE_KEN": uczelnia.pokazuj_oswiadczenie_ken,
            "SKROT_WYDZIALU_W_NAZWIE_JEDNOSTKI": (
                uczelnia.skrot_wydzialu_w_nazwie_jednostki
            ),
            "UCZELNIA_UZYWA_WYDZIALOW": uczelnia.uzywaj_wydzialow,
            "GOOGLE_ANALYTICS_PROPERTY_ID": uczelnia.google_analytics_property_id,
            "GOOGLE_VERIFICATION_CODE": uczelnia.google_verification_code,
            "WYDRUK_MARGINES_GORA": uczelnia.wydruk_margines_gora,
            "WYDRUK_MARGINES_DOL": uczelnia.wydruk_margines_dol,
            "WYDRUK_MARGINES_LEWO": uczelnia.wydruk_margines_lewo,
            "WYDRUK_MARGINES_PRAWO": uczelnia.wydruk_margines_prawo,
        }

    # Fallback — brak uczelni w request
    return {
        "UZYWAJ_PUNKTACJI_WEWNETRZNEJ": True,
        "POKAZUJ_INDEX_COPERNICUS": True,
        "POKAZUJ_PUNKTACJA_SNIP": True,
        "POKAZUJ_OSWIADCZENIE_KEN": False,
        "SKROT_WYDZIALU_W_NAZWIE_JEDNOSTKI": True,
        "UCZELNIA_UZYWA_WYDZIALOW": True,
        "GOOGLE_ANALYTICS_PROPERTY_ID": "",
        "GOOGLE_VERIFICATION_CODE": "",
        "WYDRUK_MARGINES_GORA": "2cm",
        "WYDRUK_MARGINES_DOL": "2cm",
        "WYDRUK_MARGINES_LEWO": "2cm",
        "WYDRUK_MARGINES_PRAWO": "2cm",
    }

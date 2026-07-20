"""Widoki dashboardu cache'owane `cache_page` muszą różnicować po hoście.

DLACZEGO to musi istnieć: BPP jest wielo-uczelniany —
`SiteResolutionMiddleware` rozstrzyga domenę → Site → Uczelnia per request.
`cache_page` NIE uwzględnia hosta w kluczu cache, więc bez
`vary_on_headers("Host")` odpowiedź policzona dla uczelni A jest serwowana
pod domeną uczelni B (wyciek danych między uczelniami). Cache trwa 24 h,
więc pomyłka nie jest chwilowa.

Wzorzec jak przy `bpp.views.robots_txt` (`test_seo_metadata.py`).
"""

import pytest
from django.urls import reverse

# Wszystkie widoki dashboardu owinięte w `cache_page` — każdy musi
# deklarować `Vary: Host`.
WIDOKI = [
    "admin_dashboard:weekday_stats",
    "admin_dashboard:day_of_month_activity_stats",
    "admin_dashboard:new_publications_stats",
    "admin_dashboard:cumulative_publications_stats",
    "admin_dashboard:cumulative_impact_factor_stats",
    "admin_dashboard:cumulative_points_kbn_stats",
    "admin_dashboard:charakter_formalny_stats_top90",
    "admin_dashboard:charakter_formalny_stats_remaining10",
    "admin_dashboard:charakter_formalny_stats_remaining1",
]


@pytest.mark.parametrize("nazwa_widoku", WIDOKI)
@pytest.mark.django_db
def test_widok_deklaruje_vary_host(client, admin_user, settings, nazwa_widoku):
    """Odpowiedź MUSI mieć `Vary: Host`.

    Czerwony bez `@vary_on_headers("Host")` — sam `cache_page` nagłówka
    nie ustawia, więc klucz cache jest wspólny dla wszystkich domen.
    """
    settings.ALLOWED_HOSTS = ["uczelnia1.localhost", "uczelnia2.localhost"]
    client.force_login(admin_user)

    res = client.get(reverse(nazwa_widoku), HTTP_HOST="uczelnia1.localhost")

    assert res.status_code == 200
    assert "Host" in res.get("Vary", ""), (
        f"{nazwa_widoku} nie deklaruje `Vary: Host` — cache_page zaserwuje "
        "odpowiedź jednej uczelni pod domeną innej"
    )


@pytest.mark.django_db
def test_cache_nie_przecieka_miedzy_hostami(client, admin_user, settings, mocker):
    """Dwa hosty = dwa niezależne wpisy cache, więc widok liczy się DWA razy.

    Porównywanie treści odpowiedzi niczego by nie dowiodło: na pustej bazie
    obie są identyczne niezależnie od tego, czy cache przeciekł. Liczymy
    więc, ile razy widok naprawdę policzył dane. Trafienie w cudzy wpis
    dałoby jedno wykonanie na dwa żądania.
    """
    from django.core.cache import cache

    settings.ALLOWED_HOSTS = ["uczelnia1.localhost", "uczelnia2.localhost"]
    # Domyślny cache w testach to DummyCache (patrz `settings/local.py`) —
    # `cache_page` niczego by nie zapamiętał i test nie sprawdzałby NICZEGO.
    # Podmieniamy na LocMem, żeby realnie przejść ścieżkę zapis/odczyt.
    settings.CACHES = {
        **settings.CACHES,
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-vary-host",
        },
    }
    cache.clear()
    client.force_login(admin_user)

    licznik = mocker.patch(
        "admin_dashboard.views.charakter_stats._get_charakter_counts",
        return_value=[],
    )

    url = reverse("admin_dashboard:charakter_formalny_stats_top90")

    assert client.get(url, HTTP_HOST="uczelnia1.localhost").status_code == 200
    assert licznik.call_count == 1, "pierwsze żądanie musi policzyć dane"

    res_b = client.get(url, HTTP_HOST="uczelnia2.localhost")
    assert res_b.status_code == 200
    assert "Host" in res_b.get("Vary", "")

    assert licznik.call_count == 2, (
        "drugi host dostał odpowiedź zapamiętaną dla pierwszego — cache "
        "przecieka między uczelniami"
    )

    # Kontrola: ten sam host drugi raz MUSI trafić w cache (inaczej test
    # wyżej przechodziłby dlatego, że cache w ogóle nie działa).
    assert client.get(url, HTTP_HOST="uczelnia1.localhost").status_code == 200
    assert licznik.call_count == 2, (
        "powtórzone żądanie na ten sam host nie trafiło w cache — cache_page "
        "nie działa, więc test rozdzielności hostów niczego nie dowodzi"
    )

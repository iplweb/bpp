"""Widoki dashboardu cache'owane `cache_page` deklarują `Vary: Host`.

CZEGO TE TESTY NIE DOWODZĄ: nie ma tu naprawy wycieku między uczelniami,
bo takiego wycieku nie było. `cache_page` SAM różnicuje po hoście —
`_generate_cache_key` i `_generate_cache_header_key` hashują
`request.build_absolute_uri()`, w którym host siedzi. Sprawdzone
empirycznie: `learn_cache_key` BEZ żadnego `Vary` daje różne klucze dla
dwóch domen, a `get_cache_key` drugiej domeny nie trafia we wpis pierwszej.

PO CO WIĘC `vary_on_headers("Host")`: to defense-in-depth dla
POŚREDNICZĄCYCH cache'y HTTP (proxy, CDN), które nie znają wewnętrznego
klucza Django i bez jawnego nagłówka mogłyby współdzielić odpowiedź między
domenami. BPP jest wielo-uczelniany (`SiteResolutionMiddleware`: domena →
Site → Uczelnia), więc uczciwa deklaracja `Vary` jest tania i sensowna.

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

    Czerwony bez `@vary_on_headers("Host")` — sam `cache_page` tego
    nagłówka nie ustawia (choć swój wewnętrzny klucz i tak liczy z
    hosta). Test pilnuje deklaracji dla pośredniczących cache'y HTTP.
    """
    settings.ALLOWED_HOSTS = ["uczelnia1.localhost", "uczelnia2.localhost"]
    client.force_login(admin_user)

    res = client.get(reverse(nazwa_widoku), HTTP_HOST="uczelnia1.localhost")

    assert res.status_code == 200
    assert "Host" in res.get("Vary", ""), (
        f"{nazwa_widoku} nie deklaruje `Vary: Host` — pośredniczący cache "
        "HTTP (proxy, CDN) może współdzielić odpowiedź między domenami"
    )


@pytest.mark.django_db
def test_cache_page_rozdziela_wpisy_po_hoscie(client, admin_user, settings, mocker):
    """Dwa hosty = dwa niezależne wpisy cache, więc widok liczy się DWA razy.

    UWAGA co do zakresu: ten test opisuje ZASTANE zachowanie `cache_page`,
    a nie skutek `@vary_on_headers("Host")`. Rozdzielność bierze się stąd,
    że Django hashuje `request.build_absolute_uri()` (z hostem) — jest
    ZIELONY także po zdjęciu dekoratora. Trzymamy go jako opis kontraktu,
    na którym stoi wielo-uczelnianość: gdyby Django kiedyś przestało
    kluczować po hoście, to tu wyjdzie.

    Porównywanie treści odpowiedzi niczego by nie dowiodło: na pustej bazie
    obie są identyczne niezależnie od rozdzielności cache. Liczymy więc,
    ile razy widok naprawdę policzył dane.
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

    assert licznik.call_count == 2, (
        "drugi host dostał odpowiedź zapamiętaną dla pierwszego — Django "
        "przestało kluczować cache_page po hoście (regresja kontraktu, na "
        "którym stoi wielo-uczelnianość)"
    )

    # Kontrola: ten sam host drugi raz MUSI trafić w cache (inaczej test
    # wyżej przechodziłby dlatego, że cache w ogóle nie działa).
    assert client.get(url, HTTP_HOST="uczelnia1.localhost").status_code == 200
    assert licznik.call_count == 2, (
        "powtórzone żądanie na ten sam host nie trafiło w cache — cache_page "
        "nie działa, więc test rozdzielności hostów niczego nie dowodzi"
    )

"""Widok Multiseek z report_type=pivot (tabela krzyżowa) — patrz Task 3."""

import csv
import io
import json
import re

import pytest
from django.conf import settings
from django.test import RequestFactory
from django.urls import reverse
from django.utils import translation
from multiseek.logic import STARTS_WITH
from multiseek.views import MULTISEEK_SESSION_KEY

from bpp.multiseek_registry import registry as multiseek_registry
from bpp.multiseek_registry.reports import multiseek_report_types
from bpp.tests.util import any_ciagle

PIVOT_TITLE_PREFIX = "Pivot widok test"


def _pivot_report_type_index(user):
    """Indeks pozycyjny report_type "pivot" w LISTE WŁĄCZONEJ dla usera.

    Rejestr filtruje ``multiseek_report_types`` przez ``enabled(request)`` —
    "pivot" jest publiczny więc zawsze obecny, ale jego indeks zależy od
    tego, ile innych (niepublicznych) typów zostało po drodze odfiltrowanych.
    Liczymy dynamicznie zamiast zakładać stałą wartość.
    """
    request = RequestFactory().get("/")
    request.user = user
    report_types = multiseek_registry.get_report_types(request)
    assert report_types[-1].id == "pivot"
    return len(report_types) - 1


def _set_multiseek_pivot_filter(client, user, title_prefix=PIVOT_TITLE_PREFIX):
    with translation.override(settings.LANGUAGE_CODE):
        operator = str(STARTS_WITH)

    idx = _pivot_report_type_index(user)
    session = client.session
    session[MULTISEEK_SESSION_KEY] = json.dumps(
        {
            "form_data": [
                None,
                {
                    "field": "Tytuł pracy",
                    "operator": operator,
                    "value": title_prefix,
                    "prev_op": None,
                },
            ],
            "ordering": {},
            "report_type": str(idx),
        }
    )
    session.save()


@pytest.mark.django_db
def test_pivot_results_view_zwraca_pivot(
    logged_in_client, test_user, standard_data, denorms
):
    """Po ustawieniu formularza z report_type=pivot w sesji, GET na
    /multiseek/results/?pivot_row=rok&pivot_val=liczba renderuje macierz."""
    any_ciagle(tytul_oryginalny=f"{PIVOT_TITLE_PREFIX} - alfa", rok=2024)
    denorms.flush()
    _set_multiseek_pivot_filter(logged_in_client, test_user)

    resp = logged_in_client.get(
        reverse("multiseek:results") + "?pivot_row=rok&pivot_val=liczba"
    )

    assert resp.status_code == 200
    assert "pivot" in resp.context
    assert resp.context["pivot"].row_dim.key == "rok"


@pytest.mark.django_db
def test_pivot_results_view_pomija_agregaty_listy(
    logged_in_client, test_user, standard_data, denorms
):
    """Gałąź pivota omija cache agregatów/sumy stopki listy (spec §8) —
    klucz "sumy" nie jest ustawiany, a paginator_count to uczciwa liczba
    podsumowanych rekordów (nie 0)."""
    any_ciagle(tytul_oryginalny=f"{PIVOT_TITLE_PREFIX} - beta", rok=2023)
    denorms.flush()
    _set_multiseek_pivot_filter(logged_in_client, test_user)

    resp = logged_in_client.get(
        reverse("multiseek:results") + "?pivot_row=rok&pivot_val=liczba"
    )

    assert resp.status_code == 200
    assert resp.context["paginator_count"] == 1
    assert "sumy" not in resp.context


@pytest.mark.django_db
def test_pivot_zbyt_duza_pokazuje_komunikat(
    logged_in_client, test_user, standard_data, denorms, monkeypatch
):
    """Gdy macierz przekracza limit, widok nie wysypuje się — pivot=None,
    ustawiony pivot_error, a szablon pokazuje komunikat "zawęź zapytanie"."""
    any_ciagle(tytul_oryginalny=f"{PIVOT_TITLE_PREFIX} - duza", rok=2024)
    denorms.flush()
    # Progi mieszkaja w bpp.pivot.core (tam je czyta zbuduj_pivot) — patchowanie
    # ich przez zgodnosciowy shim multiseek_registry.pivot przestawiloby martwa
    # kopie nazwy, nie bramke.
    monkeypatch.setattr("bpp.pivot.core.PIVOT_MAX_CELLS", 0)
    _set_multiseek_pivot_filter(logged_in_client, test_user)

    resp = logged_in_client.get(
        reverse("multiseek:results") + "?pivot_row=rok&pivot_val=liczba"
    )

    assert resp.status_code == 200
    assert resp.context["pivot"] is None
    assert resp.context["pivot_error"] is not None
    assert "zbyt dużą tabelę" in resp.content.decode()
    # pasek selektorów renderuje się mimo błędu
    assert 'name="pivot_row"' in resp.content.decode()


@pytest.mark.django_db
def test_pivot_renderuje_macierz_html(
    logged_in_client, test_user, standard_data, denorms
):
    """Gałąź pivota renderuje tabelę krzyżową (klasa + RAZEM) i pasek
    selektorów; zalogowany widzi linki eksportu."""
    any_ciagle(tytul_oryginalny=f"{PIVOT_TITLE_PREFIX} - gamma", rok=2024)
    denorms.flush()
    _set_multiseek_pivot_filter(logged_in_client, test_user)

    resp = logged_in_client.get(
        reverse("multiseek:results") + "?pivot_row=rok&pivot_val=liczba"
    )
    html = resp.content.decode()

    assert 'class="multiseek-pivot"' in html
    assert "RAZEM" in html
    assert 'name="pivot_row"' in html
    assert 'name="pivot_col"' in html
    assert 'name="pivot_val"' in html
    assert "export/xlsx" in html


@pytest.mark.django_db
def test_pivot_export_xlsx(logged_in_client, test_user, standard_data, denorms):
    """Eksport XLSX pivota działa (macierz, nie lista) — omija cap 5000."""
    any_ciagle(tytul_oryginalny=f"{PIVOT_TITLE_PREFIX} - delta", rok=2024)
    denorms.flush()
    _set_multiseek_pivot_filter(logged_in_client, test_user)

    resp = logged_in_client.get(
        reverse("multiseek-export", args=["xlsx"]) + "?pivot_row=rok&pivot_val=liczba"
    )
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml"
    )


@pytest.mark.django_db
def test_pivot_export_csv(logged_in_client, test_user, standard_data, denorms):
    """Eksport CSV pivota zawiera wiersz RAZEM."""
    any_ciagle(tytul_oryginalny=f"{PIVOT_TITLE_PREFIX} - epsilon", rok=2024)
    denorms.flush()
    _set_multiseek_pivot_filter(logged_in_client, test_user)

    resp = logged_in_client.get(
        reverse("multiseek-export", args=["csv"]) + "?pivot_row=rok&pivot_val=liczba"
    )
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    assert "RAZEM" in resp.content.decode()


@pytest.mark.django_db
def test_pivot_export_ukryty_dla_anonima(client, standard_data, denorms):
    """Anonim widzi tabelę krzyżową, ale NIE linki eksportu (eksport jest
    LoginRequired — link i tak dałby redirect do logowania)."""
    from django.contrib.auth.models import AnonymousUser

    any_ciagle(tytul_oryginalny=f"{PIVOT_TITLE_PREFIX} - zeta", rok=2024)
    denorms.flush()
    _set_multiseek_pivot_filter(client, AnonymousUser())

    resp = client.get(reverse("multiseek:results") + "?pivot_row=rok&pivot_val=liczba")
    html = resp.content.decode()

    assert 'class="multiseek-pivot"' in html
    assert "export/xlsx" not in html


def test_pivot_report_type_na_koncu_listy():
    """report_type jest indeksem pozycyjnym — "pivot" MUSI być ostatnim
    elementem, inaczej zapisane formularze przesuną się na inny typ."""
    assert multiseek_report_types[-1].id == "pivot"
    assert multiseek_report_types[-1].public is True
    # dotychczasowe typy zachowują pozycje (list/table na 0/1)
    assert multiseek_report_types[0].id == "list"
    assert multiseek_report_types[1].id == "table"


# --- stronicowanie i sortowanie macierzy (multiseek) ------------------------


@pytest.mark.django_db
def test_pivot_multiseek_stronicuje_wiersze(
    logged_in_client, test_user, standard_data, denorms
):
    """Ta sama funkcja co na /zapytanie/ — body pivota to WSPÓLNY partial,
    ale kontekst (pivot_widok/pivot_table) buduje każdy widok osobno."""
    for rok in range(2000, 2030):
        any_ciagle(tytul_oryginalny=f"{PIVOT_TITLE_PREFIX} - {rok}", rok=rok)
    denorms.flush()
    _set_multiseek_pivot_filter(logged_in_client, test_user)

    resp = logged_in_client.get(
        reverse("multiseek:results")
        + "?pivot_row=rok&pivot_val=liczba&pivot_per_page=25"
    )

    t = resp.context["pivot_table"]
    assert t["wszystkich_wierszy"] == 30
    assert len(t["rows"]) == 25
    assert t["is_paginated"] is True
    assert "pivot_page=2" in resp.content.decode().replace("&amp;", "&")


@pytest.mark.django_db
def test_pivot_multiseek_sortowanie_po_sumie(
    logged_in_client, test_user, standard_data, denorms
):
    # TRZY lata o różnych licznościach. Przy dwóch wierszach „sortuj po
    # sumie malejąco" i „odwróć kolejność naturalną" dają ten sam wynik,
    # więc test przechodziłby także przy zignorowanym sortowaniu. Tu:
    #   naturalna (rok malejąco): 2022, 2021, 2020
    #   odwrócona naturalna:      2020, 2021, 2022
    #   suma malejąco:            2021 (3), 2022 (2), 2020 (1)
    #   suma rosnąco:             2020, 2022, 2021
    # — cztery różne kolejności, żadnej nie da się pomylić z inną.
    for nr, rok in enumerate([2020, 2021, 2021, 2021, 2022, 2022]):
        any_ciagle(tytul_oryginalny=f"{PIVOT_TITLE_PREFIX} - {nr}", rok=rok)
    denorms.flush()
    _set_multiseek_pivot_filter(logged_in_client, test_user)

    naturalna = logged_in_client.get(
        reverse("multiseek:results") + "?pivot_row=rok&pivot_val=liczba"
    )
    assert [r["label"] for r in naturalna.context["pivot_table"]["rows"]] == [
        "2022",
        "2021",
        "2020",
    ]

    resp = logged_in_client.get(
        reverse("multiseek:results")
        + "?pivot_row=rok&pivot_val=liczba&pivot_sort=suma&pivot_dir=desc"
    )

    t = resp.context["pivot_table"]
    assert [r["label"] for r in t["rows"]] == ["2021", "2022", "2020"]
    assert [r["total"] for r in t["rows"]] == [3, 2, 1]

    rosnaco = logged_in_client.get(
        reverse("multiseek:results")
        + "?pivot_row=rok&pivot_val=liczba&pivot_sort=suma&pivot_dir=asc"
    )
    assert [r["label"] for r in rosnaco.context["pivot_table"]["rows"]] == [
        "2020",
        "2022",
        "2021",
    ]


@pytest.mark.django_db
def test_pivot_multiseek_linki_sortowania_gasza_tryb_wydruku(
    logged_in_client, test_user, standard_data, denorms
):
    """{% querystring %} przenosi CAŁY bieżący GET — a common-results.html
    odpala window.print() dla ?print=1. Bez print=None klik w sortowanie
    otwierałby okno drukowania."""
    any_ciagle(tytul_oryginalny=f"{PIVOT_TITLE_PREFIX} - print", rok=2024)
    denorms.flush()
    _set_multiseek_pivot_filter(logged_in_client, test_user)

    resp = logged_in_client.get(
        reverse("multiseek:results") + "?pivot_row=rok&pivot_val=liczba&print=1"
    )
    html = resp.content.decode().replace("&amp;", "&")

    linki = re.findall(r'class="multiseek-pivot-sort"\s+href="([^"]+)"', html)
    assert linki, "brak linków sortujących w wyrenderowanej macierzy"
    assert all("print=1" not in link for link in linki)
    assert any("pivot_sort=suma" in link for link in linki)


@pytest.mark.django_db
def test_pivot_multiseek_eksport_ignoruje_strone(
    logged_in_client, test_user, standard_data, denorms
):
    for rok in range(2000, 2030):
        any_ciagle(tytul_oryginalny=f"{PIVOT_TITLE_PREFIX} - {rok}", rok=rok)
    denorms.flush()
    _set_multiseek_pivot_filter(logged_in_client, test_user)

    resp = logged_in_client.get(
        reverse("multiseek-export", args=["csv"])
        + "?pivot_row=rok&pivot_val=liczba&pivot_per_page=25&pivot_page=2"
    )

    wiersze = list(csv.reader(io.StringIO(resp.content.decode())))
    # nagłówek + 30 lat + RAZEM
    assert len(wiersze) == 32

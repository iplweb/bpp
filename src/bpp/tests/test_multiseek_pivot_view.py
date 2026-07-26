"""Widok Multiseek z report_type=pivot (tabela krzyżowa) — patrz Task 3."""

import json

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
    monkeypatch.setattr("bpp.multiseek_registry.pivot.PIVOT_MAX_CELLS", 0)
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

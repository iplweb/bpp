"""Testy liczby zapytań dla widoków przeglądania lat (LataView / RokView).

LataView: liczba publikacji ogółem ma wynikać z już policzonych count-ów
per rok (bez osobnego SELECT COUNT(*) po całej tabeli mat).

RokView: paginator ListView już wykonuje COUNT dla danego roku — widok nie
może liczyć tego samego drugi raz, a nawigacja prev/next ma być jednym
zapytaniem zamiast dwóch EXISTS.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from bpp.tests.util import any_ciagle


def _mat_queries(ctx):
    return [q["sql"] for q in ctx.captured_queries if "bpp_rekord_mat" in q["sql"]]


@pytest.mark.django_db
def test_lata_view_jeden_skan_tabeli_mat(client, uczelnia):
    any_ciagle(rok=2020)
    any_ciagle(rok=2021)

    with CaptureQueriesContext(connection) as ctx:
        res = client.get(reverse("bpp:browse_lata"))

    assert res.status_code == 200
    assert res.context["total_publications"] == 2
    assert len(_mat_queries(ctx)) == 1


@pytest.mark.django_db
def test_rok_view_bez_redundantnych_zapytan(client, uczelnia):
    any_ciagle(rok=2019)
    any_ciagle(rok=2020)
    any_ciagle(rok=2021)

    with CaptureQueriesContext(connection) as ctx:
        res = client.get(reverse("bpp:browse_rok", args=("2020",)))

    assert res.status_code == 200
    assert res.context["prev_year"] == 2019
    assert res.context["next_year"] == 2021
    assert res.context["total_count"] == 1

    # paginator COUNT + wiersze strony + 1 zapytanie o sąsiednie lata
    assert len(_mat_queries(ctx)) <= 3


@pytest.mark.django_db
def test_rok_view_brak_sasiednich_lat(client, uczelnia):
    any_ciagle(rok=2020)

    res = client.get(reverse("bpp:browse_rok", args=("2020",)))

    assert res.status_code == 200
    assert res.context["prev_year"] is None
    assert res.context["next_year"] is None
    assert res.context["total_count"] == 1

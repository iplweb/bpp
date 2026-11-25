"""FD#527: w API obok ``typ_kbn`` / ``punkty_kbn`` są ``typ_mnisw`` /
``punkty_mnisw`` — te same dane pod nową nazwą. Dawne klucze muszą zostać
bez zmian (integracje klientów)."""

from decimal import Decimal

import pytest
from django.urls import reverse

ENDPOINTY = [
    ("wydawnictwo_ciagle", "api_v1:wydawnictwo_ciagle-detail"),
    ("wydawnictwo_zwarte", "api_v1:wydawnictwo_zwarte-detail"),
    ("praca_doktorska", "api_v1:praca_doktorska-detail"),
    ("praca_habilitacyjna", "api_v1:praca_habilitacyjna-detail"),
    ("patent", "api_v1:patent-detail"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("fikstura,nazwa_url", ENDPOINTY)
def test_fd527_api_stare_i_nowe_klucze(client, request, fikstura, nazwa_url):
    rekord = request.getfixturevalue(fikstura)
    rekord.punkty_kbn = Decimal("70.00")
    rekord.save()

    dane = client.get(reverse(nazwa_url, args=(rekord.pk,))).json()

    # Strażnik: dawne klucze są i mają dotychczasową postać.
    assert dane["punkty_kbn"] == "70.00"
    # Patent nie ma typu — klucza ``typ_kbn`` nie było tam i nadal nie ma.
    assert ("typ_kbn" in dane) == (fikstura != "patent")
    # Nowe klucze niosą dokładnie to samo.
    assert dane["punkty_mnisw"] == dane["punkty_kbn"]
    assert ("typ_mnisw" in dane) == ("typ_kbn" in dane)
    assert dane.get("typ_mnisw") == dane.get("typ_kbn")


@pytest.mark.django_db
def test_fd527_api_typ_mnisw_wskazuje_slownik_typow(client, wydawnictwo_ciagle):
    dane = client.get(
        reverse("api_v1:wydawnictwo_ciagle-detail", args=(wydawnictwo_ciagle.pk,))
    ).json()
    assert dane["typ_mnisw"].endswith(
        reverse("api_v1:typ_kbn-detail", args=(wydawnictwo_ciagle.typ_kbn_id,))
    )

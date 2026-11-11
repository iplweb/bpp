"""Ramka „Ewaluacja” na stronach źródła i wydawcy: punkty za publikację
jednego autora w bieżącej ewaluacji."""

from decimal import Decimal

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp import const
from bpp.models import Punktacja_Zrodla, Wydawca
from bpp.models.wydawca import Poziom_Wydawcy
from bpp.punkty_ewaluacji import punkty_ewaluacji_wydawcy, punkty_ewaluacji_zrodla

START = const.PBN_AKTUALNA_EWALUACJA_START
STOP = const.PBN_AKTUALNA_EWALUACJA_STOP


@pytest.mark.django_db
def test_zrodlo_najnowsza_punktacja_w_okresie(zrodlo):
    baker.make(Punktacja_Zrodla, zrodlo=zrodlo, rok=START - 1, punkty_kbn=40)
    baker.make(Punktacja_Zrodla, zrodlo=zrodlo, rok=START, punkty_kbn=100)
    baker.make(Punktacja_Zrodla, zrodlo=zrodlo, rok=START + 1, punkty_kbn=140)
    baker.make(Punktacja_Zrodla, zrodlo=zrodlo, rok=STOP + 1, punkty_kbn=200)

    wynik = punkty_ewaluacji_zrodla(zrodlo)

    assert [w["rok"] for w in wynik["lata"]] == [START, START + 1]
    assert wynik["aktualne"] == {"rok": START + 1, "punkty": Decimal("140")}


@pytest.mark.django_db
def test_zrodlo_bez_punktacji(zrodlo):
    assert punkty_ewaluacji_zrodla(zrodlo)["aktualne"] is None


@pytest.mark.django_db
def test_wydawca_poziom_i_punkty_z_aliasu():
    glowny = baker.make(Wydawca, nazwa="Główny")
    alias = baker.make(Wydawca, nazwa="Alias", alias_dla=glowny)
    baker.make(Poziom_Wydawcy, wydawca=glowny, rok=START, poziom=1)
    baker.make(Poziom_Wydawcy, wydawca=glowny, rok=START + 1, poziom=2)

    wynik = punkty_ewaluacji_wydawcy(alias)

    assert wynik["w_wykazie"]
    a = wynik["aktualne"]
    assert (a["rok"], a["poziom"]) == (START + 1, 2)
    assert (a["monografia"], a["rozdzial"], a["redakcja"]) == (200, 50, 100)
    assert [w["nazwa"] for w in wynik["lata"]][:2] == ["poziom I", "poziom II"]
    assert len(wynik["lata"]) == STOP - START + 1


@pytest.mark.django_db
def test_wydawca_spoza_wykazu():
    wydawca = baker.make(Wydawca, nazwa="Mały")
    baker.make(Poziom_Wydawcy, wydawca=wydawca, rok=START, poziom=None)

    wynik = punkty_ewaluacji_wydawcy(wydawca)

    assert not wynik["w_wykazie"]
    a = wynik["aktualne"]
    assert (a["rok"], a["poziom"]) == (STOP, 0)
    assert (a["monografia"], a["rozdzial"], a["redakcja"]) == (20, 5, 5)


@pytest.mark.django_db
def test_strona_zrodla_pokazuje_punkty(client, zrodlo):
    baker.make(Punktacja_Zrodla, zrodlo=zrodlo, rok=STOP, punkty_kbn=70)
    html = client.get(reverse("bpp:browse_zrodlo", args=(zrodlo.slug,))).content
    html = html.decode()
    assert f"Ewaluacja {START}–{STOP}" in html
    assert f"Artykuł jednego autora ({STOP})" in html
    assert "70 pkt" in html


@pytest.mark.django_db
def test_strona_wydawcy_pokazuje_punkty(client):
    wydawca = baker.make(Wydawca, nazwa="Wydawnictwo Punktowane")
    baker.make(Poziom_Wydawcy, wydawca=wydawca, rok=STOP, poziom=2)
    html = client.get(wydawca.get_absolute_url()).content.decode()
    assert f"Ewaluacja {START}–{STOP}" in html
    assert f"poziom II ({STOP})" in html
    assert "200 pkt" in html
    assert "50 pkt" in html

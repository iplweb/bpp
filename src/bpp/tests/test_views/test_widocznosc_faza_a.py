"""Faza A (#438) — testy anty-wyciekowe dla kanałów zwracających Jednostka.

Trzy kanały nie mogą zwracać jednostek `widoczna=False`:
- API (`api_v1.viewsets.struktura.JednostkaViewSet`)
- sitemapa (`django_bpp.sitemaps.JednostkaSitemap`)
- publiczny autocomplete (`bpp.views.autocomplete.units.PublicJednostkaAutocomplete`)

Bazowy `JednostkaAutocomplete` (`.all()`) jest natomiast celowo
nieprzefiltrowany — patrz test `test_bazowy_autocomplete_edytorski_widzi_ukryte`
oraz uzasadnienie w task-4-report.md.
"""

import pytest
from model_bakery import baker

from bpp.models import Jednostka
from bpp.views.autocomplete.units import (
    JednostkaAutocomplete,
    PublicJednostkaAutocomplete,
    WidocznaJednostkaAutocomplete,
)
from django_bpp.sitemaps import JednostkaSitemap


@pytest.mark.django_db
def test_sitemap_pomija_niewidoczne():
    baker.make(Jednostka, widoczna=False, nazwa="Ukryta")
    widoczna = baker.make(Jednostka, widoczna=True, nazwa="Jawna")
    items = list(JednostkaSitemap().items())
    assert widoczna in items
    assert all(j.widoczna for j in items)


@pytest.mark.django_db
def test_api_jednostka_pomija_niewidoczne(client):
    baker.make(Jednostka, widoczna=False, nazwa="UkrytaAPI")
    resp = client.get("/api/v1/jednostka/")
    assert resp.status_code == 200
    nazwy = [r["nazwa"] for r in resp.json()["results"]]
    assert "UkrytaAPI" not in nazwy


@pytest.mark.django_db
def test_public_autocomplete_pomija_niewidoczne():
    baker.make(Jednostka, widoczna=False, nazwa="UkrytaPubliczny")
    # `publiczne()` = widoczna=True i aktualna=True — jednostka musi być
    # obydwoma naraz, żeby pojawić się w kanale publicznym.
    baker.make(Jednostka, widoczna=True, aktualna=True, nazwa="JawnaPubliczny")
    view = PublicJednostkaAutocomplete()
    view.q = None
    nazwy = [j.nazwa for j in view.get_queryset()]
    assert "UkrytaPubliczny" not in nazwy
    assert "JawnaPubliczny" in nazwy


@pytest.mark.django_db
def test_widoczna_autocomplete_pomija_niewidoczne():
    baker.make(Jednostka, widoczna=False, nazwa="UkrytaWidoczna")
    baker.make(Jednostka, widoczna=True, nazwa="JawnaWidoczna")
    view = WidocznaJednostkaAutocomplete()
    view.q = None
    nazwy = [j.nazwa for j in view.get_queryset()]
    assert "UkrytaWidoczna" not in nazwy
    assert "JawnaWidoczna" in nazwy


@pytest.mark.django_db
def test_bazowy_autocomplete_edytorski_widzi_ukryte():
    """Bazowy JednostkaAutocomplete jest podpięty pod django admin
    (bpp/admin/core.py, autor.py, praca_doktorska.py,
    praca_habilitacyjna.py) — edytor musi móc przypisać autora/pracę
    do jednostki ukrytej (np. rozwiązanej, ale jeszcze historycznie
    obecnej w danych). Dlatego baza celowo NIE filtruje `widoczna`.
    """
    ukryta = baker.make(Jednostka, widoczna=False, nazwa="UkrytaEdytorska")
    view = JednostkaAutocomplete()
    view.q = None
    nazwy = [j.nazwa for j in view.get_queryset()]
    assert ukryta.nazwa in nazwy

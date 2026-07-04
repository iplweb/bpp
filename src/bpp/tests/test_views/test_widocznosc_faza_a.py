"""Faza A (#438) — testy anty-wyciekowe dla kanałów zwracających Jednostka.

Trzy kanały nie mogą zwracać jednostek `widoczna=False`:
- API (`api_v1.viewsets.struktura.JednostkaViewSet`)
- sitemapa (`django_bpp.sitemaps.JednostkaSitemap`)
- publiczny autocomplete (`bpp.views.autocomplete.units.PublicJednostkaAutocomplete`)

Bazowy `JednostkaAutocomplete` (`.all()`) jest natomiast celowo
nieprzefiltrowany co do `widoczna` — patrz test
`test_bazowy_autocomplete_edytorski_widzi_ukryte`. Skoro zwraca ukryte
jednostki, endpoint `jednostka-autocomplete` MUSI wymagać zalogowania
(inaczej anonimowy użytkownik dostaje nazwy/id jednostek `widoczna=False`)
— patrz `test_bazowy_autocomplete_wymaga_logowania` oraz uzasadnienie w
task-4-report.md.
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
    obecnej w danych). Dlatego baza celowo NIE filtruje `widoczna`
    na poziomie querysetu.
    """
    ukryta = baker.make(Jednostka, widoczna=False, nazwa="UkrytaEdytorska")
    view = JednostkaAutocomplete()
    view.q = None
    nazwy = [j.nazwa for j in view.get_queryset()]
    assert ukryta.nazwa in nazwy


@pytest.mark.django_db
def test_bazowy_autocomplete_wymaga_logowania_anonim_zablokowany(client):
    """Skoro `JednostkaAutocomplete` (`.all()`) zwraca też jednostki
    `widoczna=False`, endpoint HTTP `jednostka-autocomplete` musi być
    zagrodzony logowaniem — inaczej anonimowy użytkownik dostaje
    nazwy/id ukrytych jednostek (#438, finding Critical #1).
    """
    baker.make(Jednostka, widoczna=False, nazwa="UkrytaHTTP")
    resp = client.get("/bpp/jednostka-autocomplete/")
    # LoginRequiredMixin (braces.views) przekierowuje do loginu.
    assert resp.status_code == 302
    assert "login" in resp.url


@pytest.mark.django_db
def test_bazowy_autocomplete_zalogowany_edytor_widzi_ukryte(client, admin_user):
    """Zalogowany (staff) użytkownik nadal widzi ukryte jednostki przez
    HTTP -- to zachowanie jest wymagane dla edytora i nie może zniknąć
    razem z poprawką bezpieczeństwa.
    """
    ukryta = baker.make(Jednostka, widoczna=False, nazwa="UkrytaHTTPEdytor")
    client.force_login(admin_user)
    resp = client.get("/bpp/jednostka-autocomplete/")
    assert resp.status_code == 200
    nazwy = [r["text"] for r in resp.json()["results"]]
    assert ukryta.nazwa in nazwy


@pytest.mark.django_db
def test_widoczna_i_public_autocomplete_pozostaja_anonimowe(client):
    """`WidocznaJednostkaAutocomplete` (multiseek) i
    `PublicJednostkaAutocomplete` muszą zostać anonimowo dostępne --
    restrukturyzacja bazy pod #438 nie może ich przypadkiem zagrodzić
    logowaniem (nie dziedziczą już z gated `JednostkaAutocomplete`).
    """
    resp = client.get("/bpp/jednostka-widoczna-autocomplete/")
    assert resp.status_code == 200

    resp = client.get("/bpp/public-jednostka-autocomplete/")
    assert resp.status_code == 200

"""Nieznane klucze w obiekcie PBN (DRYF SCHEMATU) nie mogą wywalać importu.

Geneza (Rollbar, batch apoz.edu.pl 2026-06-29):
- #420 ``AssertionError: some data still left in dictionary
  dct={'reviewers': {...}}`` (2x) — PBN dorzucił do obiektu artykułu klucz
  ``reviewers``, którego parser nie konsumuje. Terminalne
  ``assert_dictionary_empty(pbn_json)`` wywalało cały import rekordu.

Zamiast twardego tripwire'a na poziomie obiektu PBN używamy miękkiego
``skonsumuj_nieobsluzone_klucze``: nieznane klucze lądują w ``adnotacje``
(nic nie ginie, greppable po ``PBN: nieobsłużone klucze``) + WARNING, a rekord
importuje się mimo dryfu. Wąskie tripwire'y na pod-słownikach (autorzy, oa,
journalIssue, naukowcy) zostają twarde — tam leftover to realny błąd, nie dryf.
"""

import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from pbn_integrator.importer import helpers


@pytest.mark.django_db
def test_skonsumuj_reviewers_do_adnotacji_bez_wyjatku():
    """Payload #420: leftover ``reviewers`` → adnotacje + brak wyjątku."""
    ret = baker.make(Wydawnictwo_Ciagle, adnotacje="")
    dct = {
        "reviewers": {
            "5e709356878c28a0473a78c0": {"name": "Dariusz", "lastName": "Grygrowski"}
        }
    }

    # nie może rzucić (dawniej: AssertionError)
    helpers.skonsumuj_nieobsluzone_klucze(dct, ret, kontekst="artykuł")

    ret.refresh_from_db()
    assert "PBN: nieobsłużone klucze" in ret.adnotacje
    assert "reviewers" in ret.adnotacje
    # klucze skonsumowane — słownik pusty
    assert dct == {}


@pytest.mark.django_db
def test_skonsumuj_pusty_slownik_noop():
    """Pusty słownik → żadnej adnotacji, żadnego zapisu."""
    ret = baker.make(Wydawnictwo_Ciagle, adnotacje="")

    helpers.skonsumuj_nieobsluzone_klucze({}, ret)

    ret.refresh_from_db()
    assert ret.adnotacje == ""


@pytest.mark.django_db
def test_skonsumuj_dokleja_do_istniejacych_adnotacji():
    """Nowe klucze dokleja się do istniejącej treści adnotacji (nic nie nadpisuje)."""
    ret = baker.make(Wydawnictwo_Ciagle, adnotacje="Coś ważnego wcześniej\n")

    helpers.skonsumuj_nieobsluzone_klucze({"cosNowego": "wartosc"}, ret)

    ret.refresh_from_db()
    assert "Coś ważnego wcześniej" in ret.adnotacje
    assert "cosNowego" in ret.adnotacje

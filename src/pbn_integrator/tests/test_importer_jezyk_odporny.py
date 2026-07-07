"""Lookup ``Jezyk`` w imporcie PBN musi znosić BRUDNE DANE słownika języków.

Geneza (Rollbar, batch apoz.edu.pl 2026-06-29):
- #411 ``MultipleObjectsReturned: get() returned more than one Jezyk`` (130x) —
  w bazie są ZDUBLOWANE rekordy ``Jezyk`` (np. dwa wskazujące ten sam
  ``pbn_api.Language``, albo dwa o skrócie z tym samym prefiksem). ``.get()``
  wywalał cały import rekordu.
- #350 ``DoesNotExist: Jezyk matching query does not exist`` (20x) — kod języka
  z PBN spoza słownika.

Oba to sygnał brudnych danych (dedup rekordów ``Jezyk`` to OSOBNY ticket), ale
żaden nie może wywalać importu: degradujemy do braku dopasowania / języka
domyślnego i lecimy dalej.

Uwaga na dane bazowe: baseline zawiera standardowe języki, a ``Jezyk.nazwa`` i
``Jezyk.skrot`` są UNIQUE — dlatego testy tworzą wyłącznie SYNTETYCZNE rekordy
(prefiks ``zz``), których w baseline nie ma.
"""

import pytest
from model_bakery import baker

from bpp.models import Jezyk
from pbn_api.models import Language
from pbn_integrator.importer import helpers


@pytest.mark.django_db
def test_znajdz_jezyk_dubel_po_pbn_uid_degraduje_do_none():
    """Dwa ``Jezyk`` wskazujące ten sam ``Language`` → ``None`` zamiast wyjątku."""
    lang = baker.make(Language, code="zz1")
    baker.make(Jezyk, nazwa="ZZ język 1a", skrot="zz1a", pbn_uid=lang)
    baker.make(Jezyk, nazwa="ZZ język 1b", skrot="zz1b", pbn_uid=lang)

    assert helpers._znajdz_jezyk("zz1") is None


@pytest.mark.django_db
def test_znajdz_jezyk_dubel_po_skrocie_degraduje_do_none():
    """Prefiks skrótu trafiający w wiele rekordów → ``None`` zamiast wyjątku."""
    baker.make(Jezyk, nazwa="ZZ język 2a", skrot="zz2a")
    baker.make(Jezyk, nazwa="ZZ język 2b", skrot="zz2b")

    # brak dopasowania po pbn_uid_id → fallback skrot__startswith='zz2' → 2 wyniki
    assert helpers._znajdz_jezyk("zz2") is None


@pytest.mark.django_db
def test_znajdz_jezyk_brak_kodu_i_pustego():
    """Kod spoza słownika oraz pusty/None → ``None`` (brak języka to nie błąd)."""
    assert helpers._znajdz_jezyk("zzbrak") is None
    assert helpers._znajdz_jezyk("") is None
    assert helpers._znajdz_jezyk(None) is None


@pytest.mark.django_db
def test_pobierz_jezyk_dubel_wraca_domyslny():
    """Przy zdublowanym ``Jezyk`` ``pobierz_jezyk`` degraduje do domyślnego."""
    lang = baker.make(Language, code="zz3")
    baker.make(Jezyk, nazwa="ZZ język 3a", skrot="zz3a", pbn_uid=lang)
    baker.make(Jezyk, nazwa="ZZ język 3b", skrot="zz3b", pbn_uid=lang)

    # domyślny (bez wskazania wołającego) to polski z baseline
    assert helpers.pobierz_jezyk("zz3") == helpers.get_jezyk_polski()


@pytest.mark.django_db
def test_pobierz_jezyk_dopasowuje_jednoznaczny():
    """Kontrola: jednoznaczny kod nadal daje właściwy język (nie degraduje)."""
    lang = baker.make(Language, code="zz4")
    solo = baker.make(Jezyk, nazwa="ZZ język 4", skrot="zz4.", pbn_uid=lang)

    assert helpers.pobierz_jezyk("zz4") == solo


@pytest.mark.django_db
def test_importuj_streszczenia_dubel_pomija_bez_wyjatku():
    """Streszczenie w zdublowanym języku → pominięte, import się nie wywala."""
    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Streszczenie

    lang = baker.make(Language, code="zz5")
    baker.make(Jezyk, nazwa="ZZ język 5a", skrot="zz5a", pbn_uid=lang)
    baker.make(Jezyk, nazwa="ZZ język 5b", skrot="zz5b", pbn_uid=lang)

    ret = baker.make(Wydawnictwo_Ciagle)
    pbn_json = {"abstracts": {"zz5": "Zusammenfassung"}}

    helpers.importuj_streszczenia(pbn_json, ret, Wydawnictwo_Ciagle_Streszczenie)

    assert Wydawnictwo_Ciagle_Streszczenie.objects.count() == 0

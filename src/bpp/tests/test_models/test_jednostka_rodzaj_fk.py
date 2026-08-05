"""Faza B (#438), III-1: FK ``Jednostka.rodzaj`` po usunięciu CharField
``rodzaj_jednostki`` — jedyne źródło prawdy.

Backfill CharField→FK (Faza A, 0451) i re-backfille (Faza B / F1 — 0459;
III-1 belt-and-braces — 0461) są odtąd testowane WYŁĄCZNIE łańcuchem
migracji (każda świeża baza migruje 0451→0461 po kolei — jeśli któryś z
RunPython-ów by się wywalił, cały test suite padnie na etapie budowy bazy)
oraz przez downstream testy (fixture ``kolo_naukowe``, ``test_wydzial.py``,
``ranking_autorow`` itp.), które zakładają wypełnione ``rodzaj``. Dawne
testy 0459 (``test_faza_b_ii1_rebackfill_rodzaj.py``) wołały funkcję
migracji bezpośrednio na PRAWDZIWYM (nie historycznym) modelu, symulując
drift ustawieniem CharField przez ``update()`` — po usunięciu kolumny nie
da się tego odtworzyć bez pełnego aparatu ``MigrationExecutor``/historical
apps, którego repo nie używa nigdzie indziej; ten test usunięto (patrz
report zadania III-1).

Tu zostaje tylko test podstawowego przypisania FK — CharField, po które
sięgały poprzednie warianty tego testu, już nie istnieje w modelu.
"""

import pytest
from model_bakery import baker

from bpp.models import Jednostka, RodzajJednostki


@pytest.mark.django_db
def test_rodzaj_fk_da_sie_przypisac():
    std = RodzajJednostki.objects.get(nazwa="Standard")
    j = baker.make(Jednostka, rodzaj=std)
    j.refresh_from_db()
    assert j.rodzaj == std

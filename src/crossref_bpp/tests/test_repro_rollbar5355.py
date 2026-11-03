"""Repro dla Rollbar #5355/#5356 — ``'QuerySet' object has no attribute 'pk'``.

``Komparator.porownaj_publisher`` przy luźnym dopasowaniu po początku nazwy
(``nazwa__istartswith``) wrzucał do ``rekordy`` cały ``QuerySet`` zamiast
instancji ``Wydawca``. ``rekord_po_stronie_bpp`` zwracał wtedy ``QuerySet``,
a importer publikacji robił na nim ``.pk`` → HTTP 500.
"""

import pytest
from model_bakery import baker

from bpp.models import Wydawca
from crossref_bpp.core import Komparator, StatusPorownania


@pytest.fixture
def bez_matchuj_wydawce(monkeypatch):
    """Wymuś ścieżkę ``nazwa__istartswith`` (``matchuj_wydawce`` nic nie zwraca)."""
    monkeypatch.setattr("crossref_bpp.core.matchuj_wydawce", lambda *a, **kw: None)


@pytest.mark.django_db
def test_porownaj_publisher_luzne_po_poczatku_nazwy_zwraca_instancje(
    bez_matchuj_wydawce,
):
    wydawca = baker.make(Wydawca, nazwa="Zxqalfa Wydawnictwo Naukowe")

    wynik = Komparator.porownaj_publisher("Zxqalfa")

    assert wynik.status == StatusPorownania.LUZNE
    assert wynik.rekordy == [wydawca]
    assert isinstance(wynik.rekord_po_stronie_bpp, Wydawca)
    assert wynik.rekord_po_stronie_bpp.pk == wydawca.pk


@pytest.mark.django_db
def test_porownaj_publisher_a_b_dwaj_rozni_wydawcy(bez_matchuj_wydawce):
    w1 = baker.make(Wydawca, nazwa="Zxqalfa Wydawnictwo")
    w2 = baker.make(Wydawca, nazwa="Zxqbeta Press")

    wynik = Komparator.porownaj_publisher("Zxqalfa/Zxqbeta")

    assert wynik.status == StatusPorownania.WYMAGA_INGERENCJI
    assert all(isinstance(r, Wydawca) for r in wynik.rekordy)
    assert {r.pk for r in wynik.rekordy} == {w1.pk, w2.pk}
    assert wynik.rekord_po_stronie_bpp is None


@pytest.mark.django_db
def test_porownaj_publisher_a_b_ten_sam_wydawca_deduplikuje(bez_matchuj_wydawce):
    wydawca = baker.make(Wydawca, nazwa="Zxqalfa Zxqbeta Press")

    # "Zxqalfa Zxqbeta" i "Zxqalfa" wskazują na tego samego wydawcę
    wynik = Komparator.porownaj_publisher("Zxqalfa Zxqbeta/Zxqalfa")

    assert wynik.status == StatusPorownania.LUZNE
    assert wynik.rekordy == [wydawca]
    assert wynik.rekord_po_stronie_bpp == wydawca


@pytest.mark.django_db
def test_importer_source_initial_wydawca_pk(bez_matchuj_wydawce):
    """Ścieżka z Rollbara: ``_source_initial_auto_match`` nie może rzucić."""
    from importer_publikacji.views.steps import _source_initial_auto_match

    wydawca = baker.make(Wydawca, nazwa="Zxqalfa Wydawnictwo Naukowe")

    class _Sesja:
        normalized_data = {"publisher": "Zxqalfa"}

    initial = _source_initial_auto_match(_Sesja())

    assert initial["wydawca"] == wydawca.pk

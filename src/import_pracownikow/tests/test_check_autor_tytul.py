"""Regresja symetryzacji ``_check_autor_needs_update`` (T3.7).

Import USTAWIA tytuł, nigdy go nie kasuje (spójne z ``_integrate_autor``, który
ustawia ``a.tytul_id`` tylko przy ``self.tytul_id is not None``). Wcześniej metoda
zwracała ``self.tytul_id != a.tytul_id`` BEZWARUNKOWO — utytułowany autor z pustym
tytułem w wierszu dawał ``zmiany_potrzebne=True`` + puste ``integrate()``.
"""

import pytest
from model_bakery import baker

from bpp.models import Autor, Tytul
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow


def _tytul(nazwa, skrot):
    # ``Tytul`` bywa seedowany w baseline (nazwa/skrot unikalne) — get_or_create,
    # by nie kolidować z istniejącymi wpisami ani nie duplikować.
    t, _ = Tytul.objects.get_or_create(nazwa=nazwa, defaults={"skrot": skrot})
    return t


@pytest.mark.django_db
def test_pusty_tytul_wiersza_nie_zawyza_zmian():
    """Autor z tytułem + wiersz bez tytułu (``tytul=None``) i bez innych zmian
    → ``check_if_integration_needed()`` NIE zwraca True z powodu tytułu."""
    tytul = _tytul("Tytuł testowy symetryzacja A", "tyt. sym. A")
    autor = baker.make(Autor, tytul=tytul)
    row = ImportPracownikowRow(
        parent=baker.make(ImportPracownikow),
        autor=autor,
        tytul=None,
        dane_znormalizowane={},
        zmiany_potrzebne=False,
    )
    row.save()
    assert row.check_if_integration_needed() is False


@pytest.mark.django_db
def test_tytul_wiersza_rozny_od_autora_wymaga_zmian():
    """Gdy wiersz MA tytuł różny od autora → nadal ``True`` (import go ustawi)."""
    tytul_autora = _tytul("Tytuł testowy symetryzacja B", "tyt. sym. B")
    tytul_wiersza = _tytul("Tytuł testowy symetryzacja C", "tyt. sym. C")
    autor = baker.make(Autor, tytul=tytul_autora)
    row = ImportPracownikowRow(
        parent=baker.make(ImportPracownikow),
        autor=autor,
        tytul=tytul_wiersza,
        dane_znormalizowane={},
        zmiany_potrzebne=False,
    )
    row.save()
    assert row.check_if_integration_needed() is True

"""``ImportPracownikow.nic_do_utworzenia`` — czy Krok 1 nie utworzy NICZEGO
nowego (wszystkie nierozstrzygnięte decyzje to auto-dopasowania ``ZGADYWANIE``
do istniejących rekordów; zero ``BRAK`` = „do utworzenia").

Steruje etykietą przycisku Kroku 1 („Przejdź do kolejnego kroku") oraz
synchronicznym skrótem do Kroku 2 (pominięcie strony live)."""

import pytest
from model_bakery import baker

from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowJednostka,
    ImportPracownikowStanowisko,
    ImportPracownikowStopien,
    ImportPracownikowTytul,
)


@pytest.mark.django_db
def test_bez_decyzji_nic_do_utworzenia():
    """Zero decyzji (wszystko twardo dopasowane) → nic nie powstanie."""
    imp = baker.make(ImportPracownikow)
    assert imp.nic_do_utworzenia is True


@pytest.mark.django_db
def test_jednostka_zgadywanie_nic_do_utworzenia():
    """Decyzja o jednostce w trybie ZGADYWANIE (match do istniejącej) niczego nie
    tworzy → nic_do_utworzenia zostaje True mimo istnienia decyzji."""
    imp = baker.make(ImportPracownikow)
    baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        tryb=ImportPracownikowJednostka.TRYB_ZGADYWANIE,
        utworzona=None,
    )
    assert imp.nic_do_utworzenia is True


@pytest.mark.django_db
def test_jednostka_brak_to_do_utworzenia():
    """Decyzja o jednostce w trybie BRAK (utwórz nową) → coś powstanie."""
    imp = baker.make(ImportPracownikow)
    baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        tryb=ImportPracownikowJednostka.TRYB_BRAK,
        utworzona=None,
    )
    assert imp.nic_do_utworzenia is False


@pytest.mark.django_db
def test_juz_rozstrzygnieta_brak_nie_liczy_sie():
    """BRAK z ustawionym ``utworzona`` (już zmaterializowana) nie jest „do
    utworzenia" — filtr patrzy tylko na nierozstrzygnięte decyzje."""
    imp = baker.make(ImportPracownikow)
    jednostka = baker.make("bpp.Jednostka")
    baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        tryb=ImportPracownikowJednostka.TRYB_BRAK,
        utworzona=jednostka,
    )
    assert imp.nic_do_utworzenia is True


@pytest.mark.django_db
def test_tytul_brak_to_do_utworzenia():
    """BRAK dowolnego słownika (tu: tytuł) też liczy się jako „do utworzenia"."""
    imp = baker.make(ImportPracownikow)
    baker.make(
        ImportPracownikowTytul,
        parent=imp,
        tryb=ImportPracownikowTytul.TRYB_BRAK,
        utworzony=None,
    )
    assert imp.nic_do_utworzenia is False


@pytest.mark.django_db
def test_stopien_i_stanowisko_brak_to_do_utworzenia():
    """Stopień oraz stanowisko w trybie BRAK również wykluczają nic_do_utworzenia."""
    imp = baker.make(ImportPracownikow)
    dec = baker.make(
        ImportPracownikowStopien,
        parent=imp,
        tryb=ImportPracownikowStopien.TRYB_BRAK,
        utworzony=None,
    )
    assert imp.nic_do_utworzenia is False
    dec.delete()

    baker.make(
        ImportPracownikowStanowisko,
        parent=imp,
        tryb=ImportPracownikowStanowisko.TRYB_BRAK,
        utworzone=None,
    )
    assert imp.nic_do_utworzenia is False

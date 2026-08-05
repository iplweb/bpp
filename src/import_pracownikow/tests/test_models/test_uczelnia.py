"""``ImportPracownikow.uczelnia_do_integracji`` i ``uczelnia_nieokreslona_a_potrzebna``
— multi-hosted: uczelnia importu (złapana z requestu) jest źródłem prawdy dla
pipeline'u w tle; gdy jej nie da się ustalić, a są jednostki „do utworzenia",
UI ma o tym GŁOŚNO ostrzec (zamiast cichego pominięcia)."""

import pytest
from model_bakery import baker

from bpp.models import Uczelnia
from import_pracownikow.models import ImportPracownikow, ImportPracownikowJednostka


@pytest.mark.django_db
def test_uczelnia_do_integracji_wprost_z_pola():
    """Ustawione ``uczelnia`` wygrywa — nawet przy >1 uczelni w systemie."""
    baker.make(Uczelnia)  # druga uczelnia — get_single_uczelnia_or_none() = None
    u = baker.make(Uczelnia)
    imp = baker.make(ImportPracownikow, uczelnia=u)
    assert imp.uczelnia_do_integracji() == u


@pytest.mark.django_db
def test_uczelnia_do_integracji_fallback_jedyna():
    """Bez ``uczelnia`` na imporcie, ale dokładnie 1 w systemie → fallback."""
    Uczelnia.objects.all().delete()
    u = baker.make(Uczelnia)
    imp = baker.make(ImportPracownikow, uczelnia=None)
    assert imp.uczelnia_do_integracji() == u


@pytest.mark.django_db
def test_uczelnia_do_integracji_none_gdy_wiele_i_brak_pola():
    """>1 uczelnia i puste ``uczelnia`` → None (bez zgadywania pierwszej-z-brzegu)."""
    baker.make(Uczelnia)
    baker.make(Uczelnia)
    imp = baker.make(ImportPracownikow, uczelnia=None)
    assert imp.uczelnia_do_integracji() is None


@pytest.mark.django_db
def test_nieokreslona_ostrzega_gdy_brak_uczelni_i_jest_co_tworzyc():
    """Uczelnia nieustalona + decyzja BRAK (do utworzenia) → ostrzegaj."""
    baker.make(Uczelnia)
    baker.make(Uczelnia)  # >1 → uczelnia_do_integracji() = None
    imp = baker.make(ImportPracownikow, uczelnia=None)
    baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        tryb=ImportPracownikowJednostka.TRYB_BRAK,
        utworzona=None,
    )
    assert imp.uczelnia_nieokreslona_a_potrzebna is True


@pytest.mark.django_db
def test_nieokreslona_nie_ostrzega_gdy_uczelnia_znana():
    """Uczelnia ustalona → brak ostrzeżenia, choćby były jednostki do utworzenia."""
    baker.make(Uczelnia)
    u = baker.make(Uczelnia)
    imp = baker.make(ImportPracownikow, uczelnia=u)
    baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        tryb=ImportPracownikowJednostka.TRYB_BRAK,
        utworzona=None,
    )
    assert imp.uczelnia_nieokreslona_a_potrzebna is False


@pytest.mark.django_db
def test_nieokreslona_nie_ostrzega_gdy_nic_do_utworzenia():
    """Uczelnia nieustalona, ale zero decyzji BRAK (nic do tworzenia) → brak
    ostrzeżenia — uczelnia nie jest wtedy potrzebna do utworzenia jednostek."""
    baker.make(Uczelnia)
    baker.make(Uczelnia)
    imp = baker.make(ImportPracownikow, uczelnia=None)
    baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        tryb=ImportPracownikowJednostka.TRYB_ZGADYWANIE,
        utworzona=None,
    )
    assert imp.uczelnia_nieokreslona_a_potrzebna is False

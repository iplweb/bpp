import pytest
from model_bakery import baker

from import_pracownikow.models import (
    AutorForm,
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowStanowisko,
    ImportPracownikowStopien,
)


def test_autorform_ma_nowe_pola_opcjonalne():
    for pole in ("email", "stopień_służbowy", "stanowisko_dydaktyczne"):
        assert pole in AutorForm.base_fields
        assert AutorForm.base_fields[pole].required is False


@pytest.mark.django_db
def test_stopnie_wymagaja_rozstrzygniecia():
    imp = baker.make(ImportPracownikow)
    assert imp.stopnie_wymagaja_rozstrzygniecia is False
    baker.make(
        ImportPracownikowStopien,
        parent=imp,
        nazwa_zrodlowa="kpt.",
        decyzja=ImportPracownikowStopien.DECYZJA_AKCEPTUJ,
        utworzony=None,
    )
    assert imp.stopnie_wymagaja_rozstrzygniecia is True


@pytest.mark.django_db
def test_stopnie_pomin_liczy_sie_jako_rozstrzygniete():
    imp = baker.make(ImportPracownikow)
    baker.make(
        ImportPracownikowStopien,
        parent=imp,
        nazwa_zrodlowa="kpt.",
        decyzja=ImportPracownikowStopien.DECYZJA_POMIN,
        utworzony=None,
    )
    assert imp.stopnie_wymagaja_rozstrzygniecia is False


@pytest.mark.django_db
def test_stanowiska_wymagaja_rozstrzygniecia():
    imp = baker.make(ImportPracownikow)
    baker.make(
        ImportPracownikowStanowisko,
        parent=imp,
        nazwa_zrodlowa="adiunkt",
        decyzja=ImportPracownikowStanowisko.DECYZJA_AKCEPTUJ,
        utworzone=None,
    )
    assert imp.stanowiska_wymagaja_rozstrzygniecia is True


@pytest.mark.django_db
def test_predykat_stopnia_overwrite_if_different():
    imp = baker.make(ImportPracownikow)
    stary = baker.make("bpp.StopienSluzbowy", nazwa="kapitan", skrot="kpt.")
    nowy = baker.make("bpp.StopienSluzbowy", nazwa="brygadier", skrot="bryg.")
    autor = baker.make("bpp.Autor", stopien_sluzbowy=stary)
    row = baker.make(
        ImportPracownikowRow,
        parent=imp,
        zmiany_potrzebne=False,
        autor=autor,
        stopien=nowy,
    )
    assert row._check_autor_needs_update(row.dane_znormalizowane or {}) is True
    row.stopien = stary
    assert row._check_autor_needs_update(row.dane_znormalizowane or {}) is False


@pytest.mark.django_db
def test_predykat_stanowiska_overwrite_if_different():
    imp = baker.make(ImportPracownikow)
    sd = baker.make("bpp.StanowiskoDydaktyczne", nazwa="profesor", skrot="prof.")
    inne = baker.make("bpp.StanowiskoDydaktyczne", nazwa="adiunkt", skrot="ad.")
    # pmp=True neutralizuje predykat „podstawowe miejsce pracy" (#4) — bez tego
    # check_if_integration_needed() dawał True nawet BEZ implementacji stanowiska
    # (fałszywie-pozytywny test).
    aj = baker.make(
        "bpp.Autor_Jednostka", stanowisko=inne, podstawowe_miejsce_pracy=True
    )
    row = baker.make(
        ImportPracownikowRow,
        parent=imp,
        zmiany_potrzebne=False,
        autor=aj.autor,
        autor_jednostka=aj,
        stanowisko_dydaktyczne=sd,
        dane_znormalizowane={},
    )
    # inne stanowisko na wierszu niż na AJ → integracja potrzebna
    assert row.check_if_integration_needed() is True
    # to samo stanowisko (pmp=True, brak innych zmian) → predykat False
    aj.stanowisko = sd
    aj.save(update_fields=["stanowisko"])
    assert row.check_if_integration_needed() is False

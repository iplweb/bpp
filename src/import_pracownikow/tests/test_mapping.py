import pytest

from import_pracownikow.mapping import (
    POLA_DOCELOWE,
    POLE_POMIN,
    dopasuj_profil,
    remapuj_wiersz,
    waliduj_mapowanie,
    zaproponuj_mapowanie,
)
from import_pracownikow.models import ProfilMapowania


def test_pola_docelowe_zawieraja_kluczowe_pola():
    klucze = {k for k, _ in POLA_DOCELOWE}
    assert {"nazwisko", "imię", "nazwa_jednostki"} <= klucze
    # Faza 3 dodaje kompozyt „osoba sklejona":
    assert "osoba_sklejona" in klucze


def test_zaproponuj_mapowanie_synonimy():
    naglowki = ["nazwisko", "imię", "jedn_org", "stanowisko", "kolumna_smieciowa"]
    prop = zaproponuj_mapowanie(naglowki)
    assert prop["nazwisko"] == "nazwisko"
    assert prop["imię"] == "imię"
    assert prop["jedn_org"] == "nazwa_jednostki"  # synonim
    assert prop["stanowisko"] == "stanowisko"
    # nieznana kolumna → pomiń
    assert prop["kolumna_smieciowa"] == POLE_POMIN


def test_zaproponuj_mapowanie_bpp_wzorzec():
    # znormalizowane nagłówki wzorca BPP
    naglowki = ["nazwa_jednostki", "wydział", "tytuł_stopień", "bpp_id"]
    prop = zaproponuj_mapowanie(naglowki)
    assert prop["nazwa_jednostki"] == "nazwa_jednostki"
    assert prop["tytuł_stopień"] == "tytuł_stopień"
    assert prop["bpp_id"] == "bpp_id"


def test_waliduj_mapowanie_wymaga_nazwisko_imie_jednostka():
    # brak jednostki → błąd
    bledy = waliduj_mapowanie({"a": "nazwisko", "b": "imię"})
    assert any("jednostk" in e.lower() for e in bledy)
    # komplet identyfikacji → OK
    assert (
        waliduj_mapowanie({"a": "nazwisko", "b": "imię", "c": "nazwa_jednostki"}) == []
    )


def test_waliduj_mapowanie_odrzuca_duplikat_pola():
    # to samo pole docelowe przypisane dwóm kolumnom → błąd
    bledy = waliduj_mapowanie(
        {"a": "nazwisko", "b": "nazwisko", "c": "imię", "d": "nazwa_jednostki"}
    )
    assert any("dwukrotnie" in e.lower() or "duplikat" in e.lower() for e in bledy)


def test_remapuj_wiersz_przepisuje_klucze_i_pomija():
    elem = {
        "jedn_org": "Katedra X",
        "nazwisko": "Kowalski",
        "kolumna_smieciowa": "xxx",
        "__xls_loc_sheet__": 0,
        "__xls_loc_row__": 7,
    }
    mapowanie = {
        "jedn_org": "nazwa_jednostki",
        "nazwisko": "nazwisko",
        "kolumna_smieciowa": "__pomin__",
    }
    out = remapuj_wiersz(elem, mapowanie)
    assert out["nazwa_jednostki"] == "Katedra X"
    assert out["nazwisko"] == "Kowalski"
    assert "kolumna_smieciowa" not in out
    assert "jedn_org" not in out
    # klucze lokalizacyjne zachowane
    assert out["__xls_loc_sheet__"] == 0
    assert out["__xls_loc_row__"] == 7


@pytest.mark.django_db
def test_dopasuj_profil_pokrycie_ponad_90pct():
    ProfilMapowania.objects.create(
        nazwa="P",
        mapowanie={
            "nazwisko": "nazwisko",
            "imię": "imię",
            "jedn_org": "nazwa_jednostki",
        },
    )
    # nagłówki pokrywają się w 100% z kluczami profilu
    p = dopasuj_profil(["nazwisko", "imię", "jedn_org"])
    assert p is not None and p.nazwa == "P"


@pytest.mark.django_db
def test_dopasuj_profil_brak_gdy_niskie_pokrycie():
    ProfilMapowania.objects.create(
        nazwa="P",
        mapowanie={"a": "nazwisko", "b": "imię", "c": "nazwa_jednostki"},
    )
    assert dopasuj_profil(["zupełnie", "inne", "naglowki", "xyz"]) is None


def test_synonimy_osoba_sklejona():
    prop = zaproponuj_mapowanie(
        ["nazwisko_i_imię", "imię_i_nazwisko", "osoba", "pracownik"]
    )
    assert prop["nazwisko_i_imię"] == "osoba_sklejona"
    assert prop["imię_i_nazwisko"] == "osoba_sklejona"
    assert prop["osoba"] == "osoba_sklejona"


def test_waliduj_mapowanie_akceptuje_osoba_sklejona_zamiast_nazwisko_imie():
    # osoba_sklejona + jednostka = komplet identyfikacji (bez osobnych nazwisko/imię)
    assert waliduj_mapowanie({"a": "osoba_sklejona", "b": "nazwa_jednostki"}) == []


def test_waliduj_mapowanie_odrzuca_gdy_brak_identyfikacji_i_osoby():
    bledy = waliduj_mapowanie({"b": "nazwa_jednostki"})
    assert any("identyfikac" in e.lower() or "osob" in e.lower() for e in bledy)

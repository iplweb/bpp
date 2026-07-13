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


def test_pola_docelowe_zawiera_drugie_imie():
    etykiety = dict(POLA_DOCELOWE)
    assert etykiety.get("drugie_imię") == "Drugie imię"


def test_zaproponuj_mapowanie_drugie_imie_synonimy():
    naglowki = [
        "drugie_imię",
        "drugie_imie",
        "drugie_imiona",
        "imię_drugie",
        "imie_drugie",
    ]
    prop = zaproponuj_mapowanie(naglowki)
    for h in naglowki:
        assert prop[h] == "drugie_imię", h


def test_waliduj_mapowanie_drugie_imie_opcjonalne_i_nie_przeszkadza():
    # komplet identyfikacji + drugie_imię → OK (drugie_imię nie jest wymagane)
    assert (
        waliduj_mapowanie(
            {
                "a": "nazwisko",
                "b": "imię",
                "c": "drugie_imię",
                "d": "nazwa_jednostki",
            }
        )
        == []
    )


def test_waliduj_mapowanie_samo_drugie_imie_nie_identyfikuje():
    # drugie_imię BEZ imię nie spełnia identyfikacji osoby
    bledy = waliduj_mapowanie(
        {"a": "nazwisko", "c": "drugie_imię", "d": "nazwa_jednostki"}
    )
    assert any("identyfikac" in e.lower() or "imię" in e.lower() for e in bledy)


def test_waliduj_mapowanie_drugie_imie_duplikat():
    bledy = waliduj_mapowanie(
        {
            "a": "nazwisko",
            "b": "imię",
            "c": "drugie_imię",
            "e": "drugie_imię",
            "d": "nazwa_jednostki",
        }
    )
    assert any("dwukrotnie" in e.lower() or "duplikat" in e.lower() for e in bledy)


def test_zaproponuj_mapowanie_daty_od_do():
    prop = zaproponuj_mapowanie(["data_od", "data_do"])
    assert prop["data_od"] == "data_zatrudnienia"
    assert prop["data_do"] == "data_końca_zatrudnienia"


def test_zaproponuj_mapowanie_glowny_zaklad_pracy():
    prop = zaproponuj_mapowanie(
        [
            "gł_zakład_pracy",
            "gl_zaklad_pracy",
            "główny_zakład_pracy",
            "glowny_zaklad_pracy",
        ]
    )
    assert prop["gł_zakład_pracy"] == "podstawowe_miejsce_pracy"
    assert prop["gl_zaklad_pracy"] == "podstawowe_miejsce_pracy"
    assert prop["główny_zakład_pracy"] == "podstawowe_miejsce_pracy"
    assert prop["glowny_zaklad_pracy"] == "podstawowe_miejsce_pracy"


def test_zaklad_pracy_nie_koliduje_z_nazwa_jednostki():
    # samo „zakład" (nazwa jednostki) NADAL → nazwa_jednostki (regres-guard).
    prop = zaproponuj_mapowanie(["zakład", "gł_zakład_pracy"])
    assert prop["zakład"] == "nazwa_jednostki"
    assert prop["gł_zakład_pracy"] == "podstawowe_miejsce_pracy"

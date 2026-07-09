from import_pracownikow.mapping import (
    POLA_DOCELOWE,
    POLE_POMIN,
    waliduj_mapowanie,
    zaproponuj_mapowanie,
)


def test_pola_docelowe_zawieraja_kluczowe_pola():
    klucze = {k for k, _ in POLA_DOCELOWE}
    assert {"nazwa_jednostki", "wydział", "nazwisko", "imię"} <= klucze
    # osoba_sklejona to Faza 3 — NIE ma jej tu:
    assert "osoba_sklejona" not in klucze


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

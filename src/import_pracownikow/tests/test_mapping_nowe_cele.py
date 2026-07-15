from import_pracownikow.mapping import (
    POLA_DOCELOWE,
    waliduj_mapowanie,
    zaproponuj_mapowanie,
)


def _cele():
    return {k for k, _ in POLA_DOCELOWE}


def test_nowe_cele_obecne():
    for cel in [
        "email",
        "stopień_służbowy",
        "stanowisko_dydaktyczne",
        "nazwisko_imię",
        "komórka_złożona",
        "nazwa_jednostki_niepelna",
    ]:
        assert cel in _cele()


def test_synonimy_prostych_celow():
    m = zaproponuj_mapowanie(["email", "funkcja", "stanowisko_dydakt", "komórka"])
    assert m["email"] == "email"
    assert m["funkcja"] == "stanowisko"  # KEY funkcji zostaje „stanowisko"
    assert m["stanowisko_dydakt"] == "stanowisko_dydaktyczne"
    assert m["komórka"] == "komórka_złożona"


def test_nazwisko_imie_identyfikuje_osobe():
    # nazwisko_imię + komórka_złożona wystarcza (osoba + jednostka)
    assert waliduj_mapowanie({"a": "nazwisko_imię", "b": "komórka_złożona"}) == []


def test_niepelna_nazwa_spelnia_wymog_jednostki():
    assert (
        waliduj_mapowanie(
            {"a": "nazwisko", "b": "imię", "c": "nazwa_jednostki_niepelna"}
        )
        == []
    )


def test_brak_jednostki_daje_blad():
    bledy = waliduj_mapowanie({"a": "nazwisko", "b": "imię"})
    assert any("jednostk" in e.lower() for e in bledy)

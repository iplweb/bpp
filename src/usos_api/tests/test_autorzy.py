from usos_api.autorzy import pobierz_pracownikow
from usos_api.client import UsosApiClient
from usos_api.tests.utils import FakeResponse, FakeSession

BASE_URL = "https://usosapps.umlub.pl/"


def uzytkownik_usos(usos_id, imie="Jan", nazwisko="Kowalski", **nadpisania):
    dane = {
        "id": usos_id,
        "first_name": imie,
        "last_name": nazwisko,
        "titles": {"before": "dr hab. n. med.", "after": ""},
        "staff_status": 2,
        "email": f"{imie.lower()}@umlub.pl",
        "external_ids": {"orcid": "0000-0002-1825-0097", "pbn_id": "5e709..."},
        "employment_positions": [],
        "employment_functions": [],
    }
    dane.update(nadpisania)
    return dane


def strona(uzytkownicy, next_page=False, total=None):
    return {
        "users": uzytkownicy,
        "next_page": next_page,
        "total": total if total is not None else len(uzytkownicy),
    }


def test_pobierz_pracownikow_laczy_kody_jednostek_w_jeden_parametr():
    session = FakeSession(FakeResponse(strona([uzytkownik_usos("1")])))
    client = UsosApiClient(BASE_URL, session=session)

    list(pobierz_pracownikow(client, ["11000D2000", "110A200000"]))

    assert session.wywolania[0]["params"]["fac_ids"] == "11000D2000|110A200000"


def test_pobierz_pracownikow_przyjmuje_tez_pojedynczy_kod_jednostki():
    session = FakeSession(FakeResponse(strona([uzytkownik_usos("1")])))
    client = UsosApiClient(BASE_URL, session=session)

    list(pobierz_pracownikow(client, "11000D2000"))

    assert session.wywolania[0]["params"]["fac_ids"] == "11000D2000"


def test_pobierz_pracownikow_stronicuje_dopoki_usos_zglasza_next_page():
    session = FakeSession(
        FakeResponse(strona([uzytkownik_usos("1"), uzytkownik_usos("2")], True, 3)),
        FakeResponse(strona([uzytkownik_usos("3")], False, 3)),
    )
    client = UsosApiClient(BASE_URL, session=session)

    pracownicy = list(pobierz_pracownikow(client, "X", rozmiar_strony=2))

    assert [p["usos_id"] for p in pracownicy] == ["1", "2", "3"]
    assert session.wywolania[0]["params"]["start"] == 0
    assert session.wywolania[1]["params"]["start"] == 2


def test_pobierz_pracownikow_normalizuje_tytuly_i_identyfikatory_zewnetrzne():
    session = FakeSession(FakeResponse(strona([uzytkownik_usos("77")])))
    client = UsosApiClient(BASE_URL, session=session)

    (pracownik,) = list(pobierz_pracownikow(client, "X"))

    assert pracownik["imie"] == "Jan"
    assert pracownik["nazwisko"] == "Kowalski"
    assert pracownik["tytul_przed"] == "dr hab. n. med."
    assert pracownik["orcid"] == "0000-0002-1825-0097"
    assert pracownik["pbn_id"] == "5e709..."


def test_pobierz_pracownikow_znosi_brak_identyfikatorow_zewnetrznych():
    # external_ids bywa pustym słownikiem albo nullem — to norma, nie błąd.
    session = FakeSession(
        FakeResponse(strona([uzytkownik_usos("77", external_ids=None)]))
    )
    client = UsosApiClient(BASE_URL, session=session)

    (pracownik,) = list(pobierz_pracownikow(client, "X"))

    assert pracownik["orcid"] is None
    assert pracownik["pbn_id"] is None


def test_pobierz_pracownikow_rozpisuje_stanowiska_wraz_z_jednostkami():
    session = FakeSession(
        FakeResponse(
            strona(
                [
                    uzytkownik_usos(
                        "77",
                        employment_positions=[
                            {
                                "position": {"name": {"pl": "adiunkt", "en": ""}},
                                "faculty": {
                                    "id": "11000D2000",
                                    "name": {"pl": "Katedra X", "en": ""},
                                },
                            }
                        ],
                    )
                ]
            )
        )
    )
    client = UsosApiClient(BASE_URL, session=session)

    (pracownik,) = list(pobierz_pracownikow(client, "X"))

    assert pracownik["stanowiska"] == [
        {
            "stanowisko": "adiunkt",
            "jednostka_usos_id": "11000D2000",
            "jednostka": "Katedra X",
        }
    ]


def test_pobierz_pracownikow_rozpisuje_funkcje_z_oznaczeniem_oficjalnosci():
    session = FakeSession(
        FakeResponse(
            strona(
                [
                    uzytkownik_usos(
                        "77",
                        employment_functions=[
                            {
                                "function": {"pl": "kierownik katedry", "en": ""},
                                "faculty": {
                                    "id": "11000D2000",
                                    "name": {"pl": "Katedra X", "en": ""},
                                },
                                "is_official": True,
                            }
                        ],
                    )
                ]
            )
        )
    )
    client = UsosApiClient(BASE_URL, session=session)

    (pracownik,) = list(pobierz_pracownikow(client, "X"))

    assert pracownik["funkcje"] == [
        {
            "funkcja": "kierownik katedry",
            "jednostka_usos_id": "11000D2000",
            "jednostka": "Katedra X",
            "oficjalna": True,
        }
    ]


def test_pobierz_pracownikow_oznacza_nauczyciela_akademickiego():
    session = FakeSession(
        FakeResponse(
            strona(
                [
                    uzytkownik_usos("1", staff_status=2),
                    uzytkownik_usos("2", staff_status=1),
                ]
            )
        )
    )
    client = UsosApiClient(BASE_URL, session=session)

    nauczyciel, pracownik = list(pobierz_pracownikow(client, "X"))

    assert nauczyciel["nauczyciel_akademicki"] is True
    assert pracownik["nauczyciel_akademicki"] is False


def test_pobierz_pracownikow_prosi_usosa_o_filtr_nauczycieli_tylko_gdy_trzeba():
    session = FakeSession(
        FakeResponse(strona([])),
        FakeResponse(strona([])),
    )
    client = UsosApiClient(BASE_URL, session=session)

    list(pobierz_pracownikow(client, "X"))
    list(pobierz_pracownikow(client, "X", tylko_nauczyciele=True))

    assert "teachers_only" not in session.wywolania[0]["params"]
    assert session.wywolania[1]["params"]["teachers_only"] == "true"

from usos_api.client import UsosApiClient
from usos_api.jednostki import pobierz_jednostki
from usos_api.tests.utils import FakeResponse, FakeSession

BASE_URL = "https://usosapps.umlub.pl/"


def jednostka_usos(fac_id, nazwa, sciezka=(), staff_count=0):
    return {
        "id": fac_id,
        "name": {"pl": nazwa, "en": ""},
        "stats": {"staff_count": staff_count},
        "path": [
            {"id": przodek, "name": {"pl": przodek, "en": ""}} for przodek in sciezka
        ],
    }


def test_pobierz_jednostki_pyta_o_poddrzewo_i_dokłada_korzen():
    session = FakeSession(
        FakeResponse(["11000D2000"]),
        FakeResponse(
            {
                "1000000000": jednostka_usos("1000000000", "Uniwersytet Medyczny"),
                "11000D2000": jednostka_usos(
                    "11000D2000", "Dział Kadr", sciezka=["1000000000"]
                ),
            }
        ),
    )
    client = UsosApiClient(BASE_URL, session=session)

    jednostki = pobierz_jednostki(client, "1000000000")

    assert [j["usos_id"] for j in jednostki] == ["1000000000", "11000D2000"]
    assert session.wywolania[0]["params"]["fac_id"] == "1000000000"
    assert session.wywolania[1]["params"]["fac_ids"] == "1000000000|11000D2000"


def test_pobierz_jednostki_wylicza_rodzica_z_ostatniego_elementu_sciezki():
    session = FakeSession(
        FakeResponse([]),
        FakeResponse(
            {
                "110A2D1S30": jednostka_usos(
                    "110A2D1S30",
                    "Sekcja do spraw Projektów",
                    sciezka=["1000000000", "1100000000", "110A2D1000"],
                )
            }
        ),
    )
    client = UsosApiClient(BASE_URL, session=session)

    (jednostka,) = pobierz_jednostki(client, "110A2D1S30")

    assert jednostka["parent_usos_id"] == "110A2D1000"
    assert jednostka["poziom"] == 3


def test_pobierz_jednostki_korzen_uczelni_nie_ma_rodzica():
    session = FakeSession(
        FakeResponse([]),
        FakeResponse({"1000000000": jednostka_usos("1000000000", "Uniwersytet")}),
    )
    client = UsosApiClient(BASE_URL, session=session)

    (jednostka,) = pobierz_jednostki(client, "1000000000")

    assert jednostka["parent_usos_id"] is None
    assert jednostka["poziom"] == 0


def test_pobierz_jednostki_przepisuje_nazwe_i_liczbe_pracownikow():
    session = FakeSession(
        FakeResponse([]),
        FakeResponse(
            {"110A200000": jednostka_usos("110A200000", "Kwestor", staff_count=54)}
        ),
    )
    client = UsosApiClient(BASE_URL, session=session)

    (jednostka,) = pobierz_jednostki(client, "110A200000")

    assert jednostka["nazwa"] == "Kwestor"
    assert jednostka["liczba_pracownikow"] == 54


def test_pobierz_jednostki_dzieli_zapytania_na_paczki():
    # URL z setkami kodów jednostek przekroczyłby limit długości adresu, więc
    # fac/faculties wołamy porcjami.
    session = FakeSession(
        FakeResponse(["B", "C"]),
        FakeResponse({"A": jednostka_usos("A", "A"), "B": jednostka_usos("B", "B")}),
        FakeResponse({"C": jednostka_usos("C", "C")}),
    )
    client = UsosApiClient(BASE_URL, session=session)

    jednostki = pobierz_jednostki(client, "A", rozmiar_paczki=2)

    assert [j["usos_id"] for j in jednostki] == ["A", "B", "C"]
    assert session.wywolania[1]["params"]["fac_ids"] == "A|B"
    assert session.wywolania[2]["params"]["fac_ids"] == "C"

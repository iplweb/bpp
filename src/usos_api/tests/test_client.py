import pytest
from requests_oauthlib import OAuth1

from usos_api.client import UsosApiClient, UsosApiError
from usos_api.tests.utils import FakeResponse, FakeSession

BASE_URL = "https://usosapps.umlub.pl/"


def test_call_sklada_url_z_base_url_i_nazwy_metody():
    session = FakeSession(FakeResponse({"id": "123"}))
    client = UsosApiClient(BASE_URL, session=session)

    client.call("services/users/user")

    assert (
        session.wywolania[0]["url"] == "https://usosapps.umlub.pl/services/users/user"
    )


def test_call_nie_dubluje_ukosnika_gdy_base_url_bez_konca():
    session = FakeSession(FakeResponse({}))
    client = UsosApiClient("https://usosapps.umlub.pl", session=session)

    client.call("services/apisrv/now")

    assert (
        session.wywolania[0]["url"] == "https://usosapps.umlub.pl/services/apisrv/now"
    )


def test_call_zwraca_zdekodowany_json():
    session = FakeSession(FakeResponse({"id": "1000000000", "name": "Uczelnia"}))
    client = UsosApiClient(BASE_URL, session=session)

    assert client.call("services/fac/faculty") == {
        "id": "1000000000",
        "name": "Uczelnia",
    }


def test_call_przekazuje_parametry_metody():
    session = FakeSession(FakeResponse({}))
    client = UsosApiClient(BASE_URL, session=session)

    client.call("services/fac/faculty", fac_id="110A200000", fields="id|name")

    assert session.wywolania[0]["params"] == {
        "fac_id": "110A200000",
        "fields": "id|name",
    }


def test_call_pomija_parametry_o_wartosci_none():
    session = FakeSession(FakeResponse({}))
    client = UsosApiClient(BASE_URL, session=session)

    client.call("services/users/staff_index", fac_ids="X", teachers_only=None)

    assert session.wywolania[0]["params"] == {"fac_ids": "X"}


def test_call_rzuca_usosapierror_gdy_usos_odmawia_dostepu():
    session = FakeSession(
        FakeResponse(
            {
                "message": "Access to method denied. Consumer signature is required.",
                "error": "method_forbidden",
                "reason": "consumer_missing",
            },
            status_code=400,
        )
    )
    client = UsosApiClient(BASE_URL, session=session)

    with pytest.raises(UsosApiError) as wyjatek:
        client.call("services/users/staff_index", fac_ids="110A200000")

    assert wyjatek.value.reason == "consumer_missing"
    assert wyjatek.value.status_code == 400
    assert "Consumer signature is required" in str(wyjatek.value)


def test_call_rzuca_usosapierror_gdy_parametr_jest_zly():
    session = FakeSession(
        FakeResponse(
            {"message": "Parameter 'fac_id' has invalid value: No such faculty."},
            status_code=400,
        )
    )
    client = UsosApiClient(BASE_URL, session=session)

    with pytest.raises(UsosApiError) as wyjatek:
        client.call("services/fac/faculty", fac_id="NIE_MA")

    assert wyjatek.value.reason is None
    assert "No such faculty" in str(wyjatek.value)


def test_call_rzuca_usosapierror_gdy_odpowiedz_nie_jest_jsonem():
    # USOS na nieistniejącą metodę oddaje 404 z pustym ciałem — bez tego
    # ValueError z .json() wyleciałby jako nieczytelny błąd dekodowania.
    session = FakeSession(FakeResponse(None, status_code=404, text=""))
    client = UsosApiClient(BASE_URL, session=session)

    with pytest.raises(UsosApiError) as wyjatek:
        client.call("services/nie/ma")

    assert wyjatek.value.status_code == 404


def test_klient_bez_consumer_key_nie_podpisuje_zadan():
    session = FakeSession(FakeResponse({}))
    client = UsosApiClient(BASE_URL, session=session)

    assert client.anonimowy is True

    client.call("services/apisrv/now")

    assert session.wywolania[0]["auth"] is None


def test_klient_z_consumer_key_podpisuje_zadania_oauth1():
    session = FakeSession(FakeResponse({}))
    client = UsosApiClient(
        BASE_URL, consumer_key="KLUCZ", consumer_secret="SEKRET", session=session
    )

    assert client.anonimowy is False

    client.call("services/users/user")

    auth = session.wywolania[0]["auth"]
    assert isinstance(auth, OAuth1)
    assert auth.client.client_key == "KLUCZ"
    assert auth.client.client_secret == "SEKRET"

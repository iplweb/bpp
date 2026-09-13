import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from usos_api.client import UsosApiClient
from usos_api.tests.test_autorzy import strona, uzytkownik_usos
from usos_api.tests.test_jednostki import jednostka_usos
from usos_api.tests.utils import FakeResponse, FakeSession

BASE_URL = "https://usosapps.umlub.pl/"


def podstaw_klienta(mocker, modul, *odpowiedzi, consumer_key=None):
    """Podmienia fabrykę klienta w module komendy na klienta z atrapą sesji."""
    session = FakeSession(*odpowiedzi)
    klient = UsosApiClient(BASE_URL, consumer_key=consumer_key, session=session)
    mocker.patch(
        f"usos_api.management.commands.{modul}.buduj_klienta"
    ).return_value = klient
    return session


def test_komenda_usos_jednostki_wypisuje_drzewo_z_liczba_pracownikow(mocker):
    podstaw_klienta(
        mocker,
        "usos_jednostki",
        FakeResponse(["11000D2000"]),
        FakeResponse(
            {
                "1000000000": jednostka_usos(
                    "1000000000", "Uniwersytet Medyczny", staff_count=2408
                ),
                "11000D2000": jednostka_usos(
                    "11000D2000", "Dział Kadr", sciezka=["1000000000"], staff_count=16
                ),
            }
        ),
    )
    wyjscie = StringIO()

    call_command("usos_jednostki", "--root", "1000000000", stdout=wyjscie)

    tekst = wyjscie.getvalue()
    assert "1000000000" in tekst
    assert "Uniwersytet Medyczny" in tekst
    assert "Dział Kadr" in tekst
    assert "16" in tekst


def test_komenda_usos_jednostki_w_trybie_json_oddaje_parsowalna_liste(mocker):
    podstaw_klienta(
        mocker,
        "usos_jednostki",
        FakeResponse([]),
        FakeResponse({"110A200000": jednostka_usos("110A200000", "Kwestor")}),
    )
    wyjscie = StringIO()

    call_command("usos_jednostki", "--root", "110A200000", "--json", stdout=wyjscie)

    dane = json.loads(wyjscie.getvalue())
    assert dane == [
        {
            "usos_id": "110A200000",
            "nazwa": "Kwestor",
            "nazwa_en": "",
            "parent_usos_id": None,
            "poziom": 0,
            "liczba_pracownikow": 0,
        }
    ]


def test_komenda_usos_autorzy_wypisuje_pracownikow(mocker):
    podstaw_klienta(
        mocker,
        "usos_autorzy",
        FakeResponse(strona([uzytkownik_usos("77", "Anna", "Nowak")])),
        consumer_key="KLUCZ",
    )
    wyjscie = StringIO()

    call_command("usos_autorzy", "--jednostka", "11000D2000", stdout=wyjscie)

    tekst = wyjscie.getvalue()
    assert "Anna" in tekst
    assert "Nowak" in tekst
    assert "0000-0002-1825-0097" in tekst


def test_komenda_usos_autorzy_bez_consumer_key_konczy_sie_czytelnym_bledem(mocker):
    podstaw_klienta(mocker, "usos_autorzy", consumer_key=None)

    with pytest.raises(CommandError) as wyjatek:
        call_command("usos_autorzy", "--jednostka", "X")

    assert "--consumer-key" in str(wyjatek.value)


def test_komenda_usos_autorzy_z_rootem_deduplikuje_osoby_z_wielu_jednostek(mocker):
    # Ta sama osoba bywa zatrudniona w kilku jednostkach — bez deduplikacji
    # zjawiłaby się w wyniku tyle razy, w ilu jednostkach siedzi.
    podstaw_klienta(
        mocker,
        "usos_autorzy",
        FakeResponse(["JEDNOSTKA_B"]),
        FakeResponse(
            {
                "JEDNOSTKA_A": jednostka_usos("JEDNOSTKA_A", "A"),
                "JEDNOSTKA_B": jednostka_usos(
                    "JEDNOSTKA_B", "B", sciezka=["JEDNOSTKA_A"]
                ),
            }
        ),
        FakeResponse(strona([uzytkownik_usos("77", "Anna", "Nowak")])),
        FakeResponse(strona([uzytkownik_usos("77", "Anna", "Nowak")])),
        consumer_key="KLUCZ",
    )
    wyjscie = StringIO()

    call_command("usos_autorzy", "--root", "JEDNOSTKA_A", "--json", stdout=wyjscie)

    dane = json.loads(wyjscie.getvalue())
    assert [osoba["usos_id"] for osoba in dane] == ["77"]


def test_komenda_usos_autorzy_respektuje_limit(mocker):
    podstaw_klienta(
        mocker,
        "usos_autorzy",
        FakeResponse(
            strona([uzytkownik_usos("1"), uzytkownik_usos("2"), uzytkownik_usos("3")])
        ),
        consumer_key="KLUCZ",
    )
    wyjscie = StringIO()

    call_command(
        "usos_autorzy", "--jednostka", "X", "--limit", "2", "--json", stdout=wyjscie
    )

    assert len(json.loads(wyjscie.getvalue())) == 2

"""Testy normalizacji, walidacji i wyszukiwania identyfikatorów ROR.

Identyfikatory użyte w testach jako poprawne to **prawdziwe** ROR-y
(Uniwersytet Medyczny w Lublinie, Harvard, MIT) — dzięki temu test sumy
kontrolnej weryfikuje implementację wobec rzeczywistego rejestru, a nie wobec
liczb wyprodukowanych tą samą funkcją, którą testujemy.

Żaden test nie dotyka sieci: ``szukaj`` jest sprawdzane na podmienionym
``requests.get``, a smoke test komendy chodzi z ``--offline``.
"""

import re
from io import StringIO

import pytest
import requests
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError

from bpp.util import ror

# Prawdziwe identyfikatory z rejestru ROR.
ROR_UMLUB = "016f61126"
ROR_HARVARD = "03vek6s52"
ROR_MIT = "042nb2s44"


@pytest.mark.parametrize(
    "wejscie",
    [
        "https://ror.org/016f61126",
        "http://ror.org/016f61126",
        "https://ror.org/016f61126/",
        "ror.org/016f61126",
        "www.ror.org/016f61126",
        "016f61126",
        "  016F61126  ",
        "HTTPS://ROR.ORG/016F61126",
    ],
)
def test_normalizuj_sprowadza_do_postaci_kanonicznej(wejscie):
    assert ror.normalizuj(wejscie) == "https://ror.org/016f61126"


@pytest.mark.parametrize("wejscie", [None, "", "   ", "https://ror.org/", "/"])
def test_normalizuj_pustych_wartosci(wejscie):
    assert ror.normalizuj(wejscie) == ""


@pytest.mark.parametrize("identyfikator", [ROR_UMLUB, ROR_HARVARD, ROR_MIT])
def test_poprawny_dla_prawdziwych_identyfikatorow(identyfikator):
    assert ror.poprawny(identyfikator) is True
    assert ror.poprawny(f"https://ror.org/{identyfikator}") is True
    assert ror.poprawny(identyfikator.upper()) is True


@pytest.mark.parametrize(
    "identyfikator",
    [
        # Litery wykluczone z alfabetu Crockforda (mylone z cyframi).
        "01i661126",
        "01l661126",
        "01o661126",
        "01u661126",
        # Nie zaczyna się od zera.
        "116f61126",
        # Za krótki / za długi.
        "016f6112",
        "016f611267",
        # Ostatnie dwa znaki muszą być cyframi.
        "016f611ab",
        # Kompletnie nie ten format.
        "Uniwersytet Medyczny",
    ],
)
def test_poprawny_odrzuca_zly_format(identyfikator):
    assert ror.poprawny(identyfikator) is False


@pytest.mark.parametrize(
    "identyfikator",
    ["016f61127", "016f61125", "03vek6s51", "042nb2s45"],
)
def test_poprawny_odrzuca_zla_sume_kontrolna(identyfikator):
    # Format przechodzi — odpada dopiero na sumie kontrolnej ISO 7064.
    assert ror.WZORZEC_IDENTYFIKATORA.match(identyfikator) is not None
    assert ror.poprawny(identyfikator) is False


@pytest.mark.parametrize("wejscie", [None, "", "   "])
def test_poprawny_pustej_wartosci_to_falsz(wejscie):
    assert ror.poprawny(wejscie) is False


@pytest.mark.parametrize(
    "identyfikator,oczekiwana",
    [(ROR_UMLUB, "26"), (ROR_HARVARD, "52"), (ROR_MIT, "44")],
)
def test_suma_kontrolna_odtwarza_cyfry_z_rejestru(identyfikator, oczekiwana):
    assert ror.suma_kontrolna(identyfikator[:-2]) == oczekiwana


@pytest.mark.parametrize(
    "wejscie", [ROR_UMLUB, f"https://ror.org/{ROR_UMLUB}", "", None, "   "]
)
def test_waliduj_przepuszcza_poprawne_i_puste(wejscie):
    assert ror.waliduj(wejscie) is None


def test_waliduj_podnosi_blad_formatu():
    with pytest.raises(ValidationError) as info:
        ror.waliduj("01i661126")

    assert info.value.code == "ror_format"
    assert "Crockforda" in " ".join(info.value.messages)


def test_waliduj_podnosi_blad_sumy_kontrolnej():
    with pytest.raises(ValidationError) as info:
        ror.waliduj("016f61127")

    assert info.value.code == "ror_suma_kontrolna"
    komunikat = " ".join(info.value.messages)
    # Komunikat ma prowadzić do poprawki, więc podaje obie wartości.
    assert "26" in komunikat
    assert "27" in komunikat


class OdpowiedzUdawana:
    """Minimalny zamiennik ``requests.Response`` na potrzeby ``szukaj``."""

    def __init__(self, dane, wyjatek_http=None):
        self._dane = dane
        self._wyjatek_http = wyjatek_http

    def raise_for_status(self):
        if self._wyjatek_http is not None:
            raise self._wyjatek_http

    def json(self):
        if isinstance(self._dane, Exception):
            raise self._dane
        return self._dane


def _podmien_get(monkeypatch, wynik, zapis=None):
    """Podmień ``requests.get`` w module ``ror`` na funkcję zwracającą ``wynik``."""

    def udawany_get(url, **kwargs):
        if zapis is not None:
            zapis["url"] = url
            zapis["kwargs"] = kwargs
        if isinstance(wynik, Exception):
            raise wynik
        return wynik

    monkeypatch.setattr(ror.requests, "get", udawany_get)


ODPOWIEDZ_V2 = {
    "number_of_results": 2,
    "items": [
        {
            "id": "https://ror.org/016f61126",
            "names": [
                {"types": ["acronym"], "value": "MUL"},
                {
                    "types": ["ror_display", "label"],
                    "value": "Medical University of Lublin",
                },
                {"types": ["label"], "value": "Uniwersytet Medyczny w Lublinie"},
            ],
            "locations": [
                {"geonames_details": {"country_name": "Poland", "name": "Lublin"}}
            ],
        },
        {
            "id": "https://ror.org/03vek6s52",
            "names": [{"types": ["label"], "value": "Harvard University"}],
            "locations": [{"geonames_details": {"country_name": "United States"}}],
        },
    ],
}

ODPOWIEDZ_V1 = {
    "number_of_results": 1,
    "items": [
        {
            "id": "https://ror.org/042nb2s44",
            "name": "Massachusetts Institute of Technology",
            "country": {"country_name": "United States", "country_code": "US"},
        }
    ],
}


def test_szukaj_parsuje_schemat_v2(monkeypatch):
    zapis = {}
    _podmien_get(monkeypatch, OdpowiedzUdawana(ODPOWIEDZ_V2), zapis)

    wynik = ror.szukaj("Uniwersytet Medyczny w Lublinie")

    assert wynik == [
        {
            "id": "https://ror.org/016f61126",
            "nazwa": "Medical University of Lublin",
            "kraj": "Poland",
        },
        {
            "id": "https://ror.org/03vek6s52",
            "nazwa": "Harvard University",
            "kraj": "United States",
        },
    ]
    assert zapis["url"] == ror.URL_API
    assert zapis["kwargs"]["params"] == {"query": "Uniwersytet Medyczny w Lublinie"}
    # Bez timeoutu komenda interaktywna mogłaby wisieć w nieskończoność.
    assert zapis["kwargs"]["timeout"] == ror.TIMEOUT


def test_szukaj_parsuje_schemat_v1(monkeypatch):
    _podmien_get(monkeypatch, OdpowiedzUdawana(ODPOWIEDZ_V1))

    assert ror.szukaj("MIT") == [
        {
            "id": "https://ror.org/042nb2s44",
            "nazwa": "Massachusetts Institute of Technology",
            "kraj": "United States",
        }
    ]


def test_szukaj_respektuje_limit(monkeypatch):
    _podmien_get(monkeypatch, OdpowiedzUdawana(ODPOWIEDZ_V2))

    wynik = ror.szukaj("cokolwiek", limit=1)

    assert len(wynik) == 1
    assert wynik[0]["id"] == "https://ror.org/016f61126"


def test_szukaj_pustej_nazwy_nie_odpytuje_sieci(monkeypatch):
    def wybuchowy_get(*args, **kwargs):
        raise AssertionError("pusta nazwa nie powinna odpytywać API")

    monkeypatch.setattr(ror.requests, "get", wybuchowy_get)

    assert ror.szukaj("") == []
    assert ror.szukaj(None) == []
    assert ror.szukaj("   ") == []


def test_szukaj_zglasza_czytelny_blad_przy_awarii_sieci(monkeypatch):
    _podmien_get(monkeypatch, requests.ConnectionError("Name or service not known"))

    with pytest.raises(ror.BladWyszukiwania) as info:
        ror.szukaj("Uniwersytet")

    komunikat = str(info.value)
    assert "API ROR" in komunikat
    assert "Name or service not known" in komunikat
    assert isinstance(info.value.__cause__, requests.RequestException)


def test_szukaj_zglasza_czytelny_blad_przy_bledzie_http(monkeypatch):
    odpowiedz = OdpowiedzUdawana(
        None, wyjatek_http=requests.HTTPError("503 Server Error")
    )
    _podmien_get(monkeypatch, odpowiedz)

    with pytest.raises(ror.BladWyszukiwania, match="503 Server Error"):
        ror.szukaj("Uniwersytet")


def test_szukaj_zglasza_blad_gdy_odpowiedz_nie_jest_jsonem(monkeypatch):
    _podmien_get(monkeypatch, OdpowiedzUdawana(ValueError("Expecting value")))

    with pytest.raises(ror.BladWyszukiwania, match="JSON"):
        ror.szukaj("Uniwersytet")


def test_szukaj_zglasza_blad_gdy_json_ma_zly_ksztalt(monkeypatch):
    _podmien_get(monkeypatch, OdpowiedzUdawana(["nie", "obiekt"]))

    with pytest.raises(ror.BladWyszukiwania, match="nieoczekiwanym kształcie"):
        ror.szukaj("Uniwersytet")


@pytest.mark.django_db
def test_komenda_offline_pokazuje_stan_i_waliduje(uczelnia, monkeypatch):
    def wybuchowy_get(*args, **kwargs):
        raise AssertionError("--offline nie może odpytywać API ROR")

    monkeypatch.setattr(ror.requests, "get", wybuchowy_get)

    # Błędną wartość ustawiamy TU, jawnie. Wcześniej test opierał się na
    # tym, że współdzielona fixtura miała ROR o złej sumie kontrolnej —
    # naprawienie fixtury cicho wydrążyłoby ten test z sensu.
    uczelnia.ror_id = "https://ror.org/01abc23"
    uczelnia.save(update_fields=["ror_id"])

    out = StringIO()
    call_command("cerif_ustaw_ror", "--offline", stdout=out)
    wynik = out.getvalue()

    assert uczelnia.nazwa in wynik
    assert "z błędnym ROR" in wynik
    assert "Nieprawidłowy identyfikator ROR" in wynik


@pytest.mark.django_db
def test_komenda_offline_uznaje_poprawny_ror(uczelnia, monkeypatch):
    monkeypatch.setattr(
        ror.requests,
        "get",
        lambda *a, **k: pytest.fail("--offline nie może odpytywać API ROR"),
    )
    uczelnia.ror_id = f"https://ror.org/{ROR_UMLUB}"
    uczelnia.save(update_fields=["ror_id"])

    out = StringIO()
    call_command("cerif_ustaw_ror", "--offline", stdout=out)
    wynik = out.getvalue()

    assert "Wszystkie uczelnie mają poprawny ROR." in wynik


@pytest.mark.django_db
def test_komenda_ustawia_ror_w_postaci_kanonicznej(uczelnia):
    # Start od pustej wartości — inaczej komenda (słusznie) raportuje
    # "bez zmian", bo fixtura ma już dokładnie ten identyfikator.
    uczelnia.ror_id = ""
    uczelnia.save(update_fields=["ror_id"])

    out = StringIO()
    call_command(
        "cerif_ustaw_ror",
        "--uczelnia",
        str(uczelnia.pk),
        "--ustaw",
        ROR_UMLUB.upper(),
        stdout=out,
    )

    uczelnia.refresh_from_db()
    assert uczelnia.ror_id == f"https://ror.org/{ROR_UMLUB}"
    assert "ROR ustawiony na" in out.getvalue()


@pytest.mark.django_db
def test_komenda_nie_zapisuje_blednej_wartosci(uczelnia):
    poprzedni = uczelnia.ror_id

    with pytest.raises(CommandError, match="Nie zapisano"):
        call_command(
            "cerif_ustaw_ror",
            "--uczelnia",
            str(uczelnia.pk),
            "--ustaw",
            "016f61127",
            stdout=StringIO(),
        )

    uczelnia.refresh_from_db()
    assert uczelnia.ror_id == poprzedni


@pytest.mark.django_db
def test_komenda_wymaga_wskazania_uczelni_do_zapisu(uczelnia):
    with pytest.raises(CommandError, match="--uczelnia"):
        call_command("cerif_ustaw_ror", "--ustaw", ROR_UMLUB, stdout=StringIO())


@pytest.mark.django_db
def test_komenda_odnajduje_uczelnie_po_skrocie(uczelnia):
    out = StringIO()
    call_command(
        "cerif_ustaw_ror", "--uczelnia", uczelnia.skrot, "--offline", stdout=out
    )

    assert uczelnia.nazwa in out.getvalue()


@pytest.mark.django_db
def test_komenda_zglasza_nieznana_uczelnie(db):
    with pytest.raises(CommandError, match="Nie ma uczelni"):
        call_command(
            "cerif_ustaw_ror", "--uczelnia", "999999", "--offline", stdout=StringIO()
        )


@pytest.mark.django_db
def test_komenda_proponuje_kandydatow_z_api(uczelnia, monkeypatch):
    # Kandydatów proponujemy dla uczelni BEZ ROR-a (albo z błędnym) —
    # fixtura ma poprawny, więc czyścimy jawnie.
    uczelnia.ror_id = ""
    uczelnia.save(update_fields=["ror_id"])

    _podmien_get(monkeypatch, OdpowiedzUdawana(ODPOWIEDZ_V2))

    out = StringIO()
    call_command("cerif_ustaw_ror", stdout=out)
    wynik = out.getvalue()

    assert "Kandydaci z API ROR" in wynik
    assert "https://ror.org/016f61126" in wynik
    assert "Medical University of Lublin" in wynik
    assert f"--uczelnia {uczelnia.pk} --ustaw https://ror.org/016f61126" in wynik


@pytest.mark.django_db
def test_komenda_przezywa_niedostepne_api(uczelnia, monkeypatch):
    uczelnia.ror_id = ""
    uczelnia.save(update_fields=["ror_id"])

    _podmien_get(monkeypatch, requests.ConnectionError("brak sieci"))

    out = StringIO()
    call_command("cerif_ustaw_ror", stdout=out)
    wynik = out.getvalue()

    # Brak sieci nie może przerwać przeglądu — podsumowanie musi się pojawić.
    assert "Kandydaci . niedostępni" in wynik
    assert "Podsumowanie" in wynik


# -- walidacja w adminie -------------------------------------------------


@pytest.mark.django_db
def test_admin_uczelni_odrzuca_bledny_ror():
    """Bez wpięcia w formularz walidator byłby martwym kodem."""
    from bpp.admin.helpers.ror_field import czysc_ror

    with pytest.raises(ValidationError):
        czysc_ror("https://ror.org/0111ttp83")


@pytest.mark.django_db
def test_admin_normalizuje_ror_do_postaci_kanonicznej():
    """W bazie nie mogą leżeć trzy zapisy tego samego identyfikatora."""
    from bpp.admin.helpers.ror_field import czysc_ror

    assert czysc_ror("016f61126") == "https://ror.org/016f61126"
    assert czysc_ror("ror.org/016f61126") == "https://ror.org/016f61126"
    assert czysc_ror("  ") == ""


def test_przyklad_z_help_text_jest_poprawnym_ror():
    """Regresja: w help_text obu pól był ROR z błędną sumą kontrolną.

    Redakcja kopiująca przykład dostawała odrzucenie przez walidację —
    czyli dokumentacja pola uczyła, jak zrobić błąd.
    """
    from bpp.models import Jednostka, Uczelnia

    for model in (Uczelnia, Jednostka):
        pole = model._meta.get_field("ror_id")
        przyklady = re.findall(r"https://ror\.org/\S+", pole.help_text)
        assert przyklady, f"{model.__name__}: brak przykładu w help_text"
        for przyklad in przyklady:
            assert ror.poprawny(przyklad.rstrip(" .()")), przyklad

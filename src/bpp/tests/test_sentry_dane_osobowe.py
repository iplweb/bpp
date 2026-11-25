"""Czyszczenie danych osobowych po wartości (Relay) w :mod:`bpp.sentry_config`.

Relay nie zgłasza błędów w konfiguracji — reguła z literówką albo zły regex
po prostu nic nie czyszczą. Dlatego każda reguła ma tu swój przypadek, a
osobna grupa pilnuje, żeby identyfikatory bibliograficzne (ORCID, DOI, ISBN,
ISSN, id PBN) i numery wersji przechodziły nietknięte.
"""

import json

import pytest
import sentry_sdk
from sentry_relay.processing import validate_pii_config
from sentry_sdk.integrations.logging import _IGNORED_LOGGERS

from bpp import sentry_config
from bpp.sentry_config import opcje_sentry, wyczysc_dane_osobowe
from bpp.tests.test_zglaszanie_bledow import AtrapaTransportu

DANE_OSOBOWE = [
    ("email", "jan.kowalski@uczelnia.example"),
    ("ipv4", "83.12.4.5"),
    ("ipv6", "2001:db8:85a3::8a2e:370:7334"),
    ("pesel", "44051401359"),
    ("karta", "4111 1111 1111 1111"),
    ("iban", "PL61109010140000071219812874"),
    ("nrb_ze_spacjami", "PL61 1090 1014 0000 0712 1981 2874"),
    ("nrb_bez_pl", "61 1090 1014 0000 0712 1981 2874"),
    ("bearer", "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc"),
    ("haslo_w_url", "postgres://bpp:TajneHaslo1@dbserver:5432/bpp"),
]

#: Fragment, który NIE może przetrwać czyszczenia (dla danego przypadku).
SEDNO = {
    "haslo_w_url": "TajneHaslo1",
    "bearer": "eyJhbGciOiJIUzI1NiJ9",
}

NIE_RUSZAC = [
    ("orcid", "0000-0002-1825-0097"),
    ("doi", "10.1016/j.cell.2020.01.001"),
    ("isbn", "978-83-01-14215-3"),
    ("isbn_bez_kresek", "9788301142153"),
    ("issn", "0028-0836"),
    ("pbn_id", "5e709189878c28a04737dc6f"),
    ("wersja", "2026.11.24.1"),
    ("data", "2026-11-24"),
    ("uuid", "123e4567-e89b-12d3-a456-426614174000"),
    ("rok_i_strony", "2024, s. 123-145"),
]


def _zdarzenie(wartosc):
    """Zdarzenie w kształcie wysyłanym przez SDK, z wartością w każdym
    miejscu, w którym realnie trafiają się dane osobowe."""
    return {
        "event_id": "a" * 32,
        "level": "error",
        "platform": "python",
        "tags": {"DJANGO_BPP_HOSTNAME": "bpp.example"},
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": f"padło dla {wartosc}",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "bpp/views.py",
                                "function": "widok",
                                "module": "bpp.views",
                                "lineno": 10,
                                "context_line": "    raise ValueError(x)",
                                "vars": {
                                    "x": repr(wartosc),
                                    "obiekt": f"<BppUser: {wartosc}>",
                                },
                            }
                        ]
                    },
                }
            ]
        },
        "breadcrumbs": {"values": [{"message": f"log: {wartosc}"}]},
        "extra": {"cokolwiek": f"opis {wartosc}"},
        "request": {"data": {"uwagi": f"proszę o kontakt {wartosc}"}},
    }


@pytest.mark.parametrize("nazwa,wartosc", DANE_OSOBOWE)
def test_dane_osobowe_znikaja_z_kazdego_miejsca(nazwa, wartosc):
    wynik = wyczysc_dane_osobowe(_zdarzenie(wartosc))

    tekst = json.dumps(wynik, ensure_ascii=False)
    assert SEDNO.get(nazwa, wartosc) not in tekst, nazwa
    # zdarzenie nadal jest czytelne — zostaje tekst wokół zamazanej wartości
    assert "padło dla" in wynik["exception"]["values"][0]["value"]
    assert "bpp_pii_relay" not in wynik.get("tags", {})


@pytest.mark.parametrize("nazwa,wartosc", NIE_RUSZAC)
def test_identyfikatory_bibliograficzne_przechodza(nazwa, wartosc):
    wynik = wyczysc_dane_osobowe(_zdarzenie(wartosc))

    assert wartosc in wynik["exception"]["values"][0]["value"], nazwa
    assert wartosc in wynik["extra"]["cokolwiek"], nazwa


def test_konfiguracja_przechodzi_walidacje_relaya():
    """Błędny selektor nie wywala się przy imporcie, tylko przy KAŻDYM
    zdarzeniu (wtedy idzie ono bez czyszczenia) — łapiemy to tutaj."""
    validate_pii_config(json.dumps(sentry_config.KONFIGURACJA_PII))


def test_kod_zrodlowy_i_sciezki_nie_sa_czyszczone():
    zdarzenie = _zdarzenie("x")
    ramka = zdarzenie["exception"]["values"][0]["stacktrace"]["frames"][0]
    ramka["context_line"] = '    ADMIN = "admin@example.com"  # 10.0.0.1'
    ramka["filename"] = "bpp/a@b.pl/10.0.0.1.py"

    wynik = wyczysc_dane_osobowe(zdarzenie)

    ramka = wynik["exception"]["values"][0]["stacktrace"]["frames"][0]
    assert ramka["context_line"] == '    ADMIN = "admin@example.com"  # 10.0.0.1'
    assert ramka["filename"] == "bpp/a@b.pl/10.0.0.1.py"


def test_tagi_zostaja_slownikiem_i_bez_meta():
    wynik = wyczysc_dane_osobowe(_zdarzenie("jan@x.pl"))

    assert wynik["tags"]["DJANGO_BPP_HOSTNAME"] == "bpp.example"
    assert "_meta" not in wynik


def test_awaria_relaya_nie_gubi_zdarzenia(monkeypatch, caplog):
    def wybuch(konfiguracja, event):
        raise RuntimeError("relay padł")

    monkeypatch.setattr(sentry_config, "pii_strip_event", wybuch)

    wynik = wyczysc_dane_osobowe(_zdarzenie("jan@x.pl"))

    assert wynik["exception"]["values"][0]["type"] == "ValueError"
    assert wynik["tags"]["bpp_pii_relay"] == "blad"
    assert "relay padł" in caplog.text


def test_brak_relaya_nie_gubi_zdarzenia(monkeypatch):
    monkeypatch.setattr(sentry_config, "pii_strip_event", None)

    wynik = wyczysc_dane_osobowe(_zdarzenie("jan@x.pl"))

    assert wynik["tags"]["bpp_pii_relay"] == "brak"


def _wyslij_przez_sdk(funkcja):
    """Pełna ścieżka SDK z before_send i scrubberem z ``opcje_sentry()``."""
    opcje = opcje_sentry()
    transport = AtrapaTransportu()
    sentry_sdk.init(
        dsn="https://klucz@glitchtip.invalid/1",
        transport=transport,
        default_integrations=False,
        auto_enabling_integrations=False,
        before_send=opcje["before_send"],
        event_scrubber=opcje["event_scrubber"],
    )
    try:
        try:
            funkcja()
        except ValueError as e:
            sentry_sdk.capture_exception(e)
    finally:
        sentry_sdk.get_global_scope().set_client(None)
    return transport.zdarzenia


# Sklejane, żeby pełna wartość nie trafiła do linii kodu w pre/post_context
# ramki — kod źródłowy celowo NIE jest czyszczony.
EMAIL = "jan.kowalski" + "@uczelnia.example"
PESEL = "4405140" + "1359"


class _Uzytkownik:
    def __repr__(self):
        return f"<BppUser: {EMAIL}>"


def test_end_to_end_zmienne_lokalne_zostaja_ale_bez_danych_osobowych():
    def widok(uzytkownik, numer):
        raise ValueError(f"nie wysłano do {EMAIL}")

    zdarzenia = _wyslij_przez_sdk(lambda: widok(_Uzytkownik(), PESEL))

    (zdarzenie,) = zdarzenia
    tekst = json.dumps(zdarzenie, ensure_ascii=False)
    assert EMAIL not in tekst
    assert PESEL not in tekst
    wyjatek = zdarzenie["exception"]["values"][0]
    assert wyjatek["value"] == "nie wysłano do [email]"
    ramka = wyjatek["stacktrace"]["frames"][-1]
    assert ramka["vars"]["uzytkownik"] == "<BppUser: [email]>"
    assert ramka["vars"]["numer"] == "'[pesel]'"


def test_end_to_end_awaria_relaya_nie_zapetla_sie(monkeypatch):
    """Błąd Relaya jest logowany, ale ten log nie może wrócić do Sentry
    (inaczej znów przeszedłby przez before_send)."""

    def wybuch(konfiguracja, event):
        raise RuntimeError("relay padł")

    monkeypatch.setattr(sentry_config, "pii_strip_event", wybuch)

    def widok():
        raise ValueError("padło")

    zdarzenia = _wyslij_przez_sdk(widok)

    assert len(zdarzenia) == 1
    assert zdarzenia[0]["tags"]["bpp_pii_relay"] == "blad"
    assert sentry_config.__name__ in _IGNORED_LOGGERS

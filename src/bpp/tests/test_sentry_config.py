"""Testy :mod:`bpp.sentry_config` — inicjalizacja Sentry/GlitchTip."""

import smtplib
from unittest import mock

import sentry_sdk
from django.conf import settings as django_settings
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from bpp import sentry_config
from bpp.sentry_config import (
    ZAMAZANE,
    configure_sentry,
    lista_pol_do_zamazania,
    opcje_sentry,
    zamaz_parametry_url,
    zbuduj_before_send,
)
from bpp.tests.test_zglaszanie_bledow import AtrapaTransportu
from django_bpp.version import VERSION


def test_bez_dsn_sentry_nie_startuje(settings, monkeypatch):
    settings.SENTRY_DSN = ""
    monkeypatch.setattr(sentry_config, "_initialized", False)
    with mock.patch.object(sentry_sdk, "init") as init:
        assert configure_sentry() is False
    init.assert_not_called()


def test_z_dsn_sentry_startuje_raz(settings, monkeypatch):
    settings.SENTRY_DSN = "https://klucz@glitchtip.invalid/1"
    monkeypatch.setattr(sentry_config, "_initialized", False)
    with mock.patch.object(sentry_sdk, "init") as init:
        assert configure_sentry() is True
        assert configure_sentry() is True
    init.assert_called_once()
    assert init.call_args.kwargs["dsn"] == "https://klucz@glitchtip.invalid/1"


def test_ustawienia_testowe_nie_maja_dsn():
    assert django_settings.SENTRY_DSN == ""


def test_opcje_domyslne(settings):
    settings.SENTRY_DSN = "https://klucz@glitchtip.invalid/1"
    settings.SENTRY_ENVIRONMENT = ""
    settings.SENTRY_TRACES_SAMPLE_RATE = 0.0
    settings.SENTRY_SEND_DEFAULT_PII = False
    settings.ROLLBAR = {**settings.ROLLBAR, "environment": "staging"}

    opcje = opcje_sentry()

    assert opcje["environment"] == "staging"  # jak Rollbar
    assert opcje["release"] == VERSION
    assert opcje["traces_sample_rate"] is None  # śledzenie wyłączone
    assert opcje["send_default_pii"] is False
    rodzaje = {type(i) for i in opcje["integrations"]}
    assert rodzaje == {DjangoIntegration, CeleryIntegration, LoggingIntegration}
    # MCP/Starlette itp. łapałyby to, czego mcp_server celowo nie zgłasza.
    assert opcje["auto_enabling_integrations"] is False
    logging_int = next(
        i for i in opcje["integrations"] if isinstance(i, LoggingIntegration)
    )
    # Jak Rollbar: logger.error NIE staje się automatycznie zdarzeniem.
    assert logging_int._handler is None


def test_opcje_jawne(settings):
    settings.SENTRY_ENVIRONMENT = "glitchtip-test"
    settings.SENTRY_TRACES_SAMPLE_RATE = 0.25
    settings.SENTRY_SEND_DEFAULT_PII = True

    opcje = opcje_sentry()

    assert opcje["environment"] == "glitchtip-test"
    assert opcje["traces_sample_rate"] == 0.25
    assert opcje["send_default_pii"] is True


def test_lista_pol_zawiera_nasze_i_code():
    pola = lista_pol_do_zamazania()
    assert "code" in pola
    assert "pbn_token" in pola
    assert "password" in pola
    assert len(pola) == len(set(pola))


def test_zamaz_parametry_url():
    pola = {"code", "token"}
    assert zamaz_parametry_url("code=abc&state=x", pola) == (f"code={ZAMAZANE}&state=x")
    assert (
        zamaz_parametry_url("https://bpp.example/orcid/callback/?code=abc", pola)
        == f"https://bpp.example/orcid/callback/?code={ZAMAZANE}"
    )
    # bez wrażliwych parametrów — bez zmian (także kolejność / kodowanie)
    assert zamaz_parametry_url("a=1&b=%20", pola) == "a=1&b=%20"
    assert zamaz_parametry_url("", pola) == ""
    assert zamaz_parametry_url(None, pola) is None


def _zdarzenie_z_wyjatkiem(exc):
    return {"level": "error", "exception": {}}, {"exc_info": (type(exc), exc, None)}


def test_before_send_ignoruje_jak_rollbar():
    before_send = zbuduj_before_send(
        [(smtplib.SMTPAuthenticationError, "ignored")], set(), "bpp.example"
    )
    zdarzenie, hint = _zdarzenie_z_wyjatkiem(
        smtplib.SMTPAuthenticationError(535, b"zle haslo")
    )
    assert before_send(zdarzenie, hint) is None

    # inna klasa z rodziny SMTPException — przechodzi (jak w Rollbarze)
    zdarzenie, hint = _zdarzenie_z_wyjatkiem(smtplib.SMTPRecipientsRefused({}))
    assert before_send(zdarzenie, hint) is not None


def test_before_send_nadpisuje_poziom():
    before_send = zbuduj_before_send([(KeyError, "critical")], set(), "h")
    zdarzenie, hint = _zdarzenie_z_wyjatkiem(KeyError("x"))
    assert before_send(zdarzenie, hint)["level"] == "fatal"


def test_before_send_tag_hosta_i_zamazanie_requestu():
    before_send = zbuduj_before_send([], {"code"}, "bpp.example")
    zdarzenie = {
        "request": {
            "query_string": "code=tajny&x=1",
            "headers": {"Referer": "https://bpp.example/cb/?code=tajny"},
        }
    }
    wynik = before_send(zdarzenie, {})

    assert wynik["tags"]["DJANGO_BPP_HOSTNAME"] == "bpp.example"
    assert "tajny" not in wynik["request"]["query_string"]
    # Relay normalizuje nagłówki do listy par
    assert "tajny" not in str(wynik["request"]["headers"])


def test_filtry_z_ustawien_dzialaja_end_to_end(settings):
    """Pełna ścieżka SDK: before_send z opcji odrzuca wyciszony wyjątek."""
    settings.ROLLBAR = {
        **settings.ROLLBAR,
        "exception_level_filters": [(smtplib.SMTPAuthenticationError, "ignored")],
    }
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
            raise smtplib.SMTPAuthenticationError(535, b"zle haslo")
        except smtplib.SMTPAuthenticationError as e:
            sentry_sdk.capture_exception(e)

        def oauth(code, haslo_pbn):
            raise ValueError("padło")

        # sklejane, żeby wartość nie pojawiła się w linii kodu ramki
        code = "kod-" + "autoryzacyjny"
        try:
            oauth(code, "x")
        except ValueError as e:
            with sentry_sdk.new_scope() as scope:
                scope.set_extra("pbn_token", "sekret")
                sentry_sdk.capture_exception(e)
    finally:
        sentry_sdk.get_global_scope().set_client(None)

    zdarzenia = [k.get_event() for k in transport.koperty if k.get_event()]
    assert len(zdarzenia) == 1  # SMTPAuthenticationError odrzucony
    (zdarzenie,) = zdarzenia
    assert "sekret" not in str(zdarzenie["extra"])
    assert "kod-autoryzacyjny" not in str(zdarzenie["exception"])


def test_handler_sentry_podpiety_tam_gdzie_rollbar():
    loggery = django_settings.LOGGING["loggers"]
    for nazwa, konfig in loggery.items():
        if "rollbar" in konfig.get("handlers", []):
            assert "sentry" in konfig["handlers"], nazwa
    assert (
        django_settings.LOGGING["handlers"]["sentry"]["class"]
        == "sentry_sdk.integrations.logging.EventHandler"
    )

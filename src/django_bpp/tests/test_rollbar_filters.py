"""Wyciszanie błędów poczty w Rollbarze jest opt-in per instalacja.

Kontekst (Rollbar #1554, #379 — bpp.umlub.pl): serwer SMTP uczelni odrzuca
poświadczenia (``535 5.7.3 Authentication unsuccessful``). To awaria po
stronie administratorów poczty klienta, której nie naprawimy kodem, a każde
wystąpienie zakłada w Rollbarze osobny item. Wyciszamy — ale WYŁĄCZNIE na tej
instalacji, bo na pozostałych niedziałająca poczta to realny problem.
"""

import smtplib

import rollbar

from django_bpp.rollbar_filters import zbuduj_exception_level_filters


def _poziom(filters, wyjatek):
    """Odpytuje filtry tak, jak zrobi to pyrollbar przy raportowaniu."""
    for cls, poziom in filters:
        if isinstance(wyjatek, cls):
            return poziom
    return None


def test_domyslnie_bledy_poczty_sa_raportowane():
    filters = zbuduj_exception_level_filters()

    assert _poziom(filters, smtplib.SMTPAuthenticationError(535, b"nope")) is None


def test_wlaczona_flaga_wycisza_bledy_uwierzytelniania_smtp():
    filters = zbuduj_exception_level_filters(ignoruj_bledy_poczty=True)

    assert _poziom(filters, smtplib.SMTPAuthenticationError(535, b"nope")) == "ignored"


def test_wlaczona_flaga_wycisza_cala_rodzine_bledow_smtp():
    """Awaria „poczta nie działa" ma wiele wcieleń, nie tylko 535."""
    filters = zbuduj_exception_level_filters(ignoruj_bledy_poczty=True)

    assert _poziom(filters, smtplib.SMTPConnectError(421, b"busy")) == "ignored"
    assert _poziom(filters, smtplib.SMTPServerDisconnected("bye")) == "ignored"


def test_flaga_nie_wycisza_bledow_spoza_poczty():
    """Wyciszenie ma być chirurgiczne — nie zasłaniać niczego innego."""
    filters = zbuduj_exception_level_filters(ignoruj_bledy_poczty=True)

    assert _poziom(filters, ConnectionRefusedError("redis")) is None
    assert _poziom(filters, ValueError("cokolwiek")) is None


def test_ustawienia_faktycznie_wpinaja_filtry_do_rollbara():
    """Sama funkcja nic nie da, jeśli nikt jej nie zawoła w ``settings``."""
    from django.conf import settings

    assert "exception_level_filters" in settings.ROLLBAR
    # W testach flaga jest wyłączona → żadnych wyciszeń. To jest też asercja
    # bezpieczeństwa: domyślna instalacja NIE gubi błędów.
    assert settings.ROLLBAR["exception_level_filters"] == []


def test_pyrollbar_faktycznie_honoruje_nasz_format_filtrow(monkeypatch):
    """Kontrakt z pyrollbarem: nasze krotki muszą działać w ``_is_ignored``.

    Bez tego testu literówka w formacie (np. ``"ignore"`` zamiast
    ``"ignored"``) przeszłaby niezauważona — filtry są danymi, nie kodem.
    """
    filters = zbuduj_exception_level_filters(ignoruj_bledy_poczty=True)
    monkeypatch.setitem(rollbar.SETTINGS, "exception_level_filters", filters)

    assert rollbar._is_ignored(smtplib.SMTPAuthenticationError(535, b"nope"))
    assert not rollbar._is_ignored(ValueError("cokolwiek"))

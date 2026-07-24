"""Wyciszanie błędów uwierzytelniania SMTP w Rollbarze — opt-in per instalacja.

Kontekst (Rollbar #379 i #1554 — bpp.umlub.pl): serwer SMTP uczelni odrzuca
poświadczenia (``535 5.7.3 Authentication unsuccessful``). To awaria po stronie
administratorów poczty klienta, której nie naprawimy kodem. Wyciszamy — ale
WYŁĄCZNIE na tej instalacji i WYŁĄCZNIE ten jeden wyjątek.
"""

import smtplib
import sys

import rollbar

from django_bpp.rollbar_filters import zbuduj_exception_level_filters


def _wyslane_payloady(monkeypatch, filters, wyjatek):
    """Przepuszcza ``wyjatek`` przez PRAWDZIWĄ ścieżkę raportowania pyrollbara.

    Świadomie NIE odpytujemy ``rollbar._is_ignored`` — ta funkcja nie jest
    w pyrollbar 1.4.0 nigdzie wywoływana (jedyne wystąpienie to jej własna
    definicja). Realne tłumienie idzie przez ``_filtered_level`` →
    ``events.on_exception_info(level=...)`` → ``filters.basic.filter_by_level``.
    Test odpytujący martwy kod dawałby fałszywą pewność dokładnie tam, gdzie
    ma jej dostarczać.
    """
    wyslane = []
    # `report_exc_info` nic nie robi, dopóki pyrollbar nie przejdzie `init()`
    # — a w testach nie przechodzi (brak tokena). Inicjujemy więc jawnie,
    # tokenem-atrapą, i przechwytujemy wysyłkę zamiast jej blokować.
    monkeypatch.setattr(rollbar, "_initialized", True)
    monkeypatch.setattr(rollbar, "send_payload", lambda p, t: wyslane.append(p))
    monkeypatch.setitem(rollbar.SETTINGS, "access_token", "atrapa")
    monkeypatch.setitem(rollbar.SETTINGS, "exception_level_filters", filters)
    monkeypatch.setitem(rollbar.SETTINGS, "handler", "blocking")
    monkeypatch.setitem(rollbar.SETTINGS, "enabled", True)

    try:
        raise wyjatek
    except BaseException:
        rollbar.report_exc_info(sys.exc_info())

    return wyslane


def test_domyslnie_bledy_smtp_sa_raportowane(monkeypatch):
    wyslane = _wyslane_payloady(
        monkeypatch,
        zbuduj_exception_level_filters(),
        smtplib.SMTPAuthenticationError(535, b"nope"),
    )

    assert len(wyslane) == 1


def test_wlaczona_flaga_naprawde_nie_wysyla_bledu_uwierzytelniania(monkeypatch):
    """Realna ścieżka wysyłki, nie sam kształt listy filtrów."""
    wyslane = _wyslane_payloady(
        monkeypatch,
        zbuduj_exception_level_filters(ignoruj_bledy_uwierzytelniania_smtp=True),
        smtplib.SMTPAuthenticationError(535, b"nope"),
    )

    assert wyslane == []


def test_flaga_nie_wycisza_bledow_poczty_wynikajacych_z_NASZYCH_danych(monkeypatch):
    """``SMTPRecipientsRefused`` to zły adres w naszej bazie — chcemy wiedzieć.

    Zakres wyciszenia jest celowo wąski: awaria po stronie klienta to problem
    uwierzytelniania, a nie każdy błąd poczty. Odrzucony odbiorca i odrzucony
    nadawca wskazują na nasze dane/konfigurację i muszą być widoczne także na
    instalacji z wyciszeniem.
    """
    filters = zbuduj_exception_level_filters(ignoruj_bledy_uwierzytelniania_smtp=True)

    for wyjatek in (
        smtplib.SMTPRecipientsRefused({"zly@adres": (550, b"no such user")}),
        smtplib.SMTPSenderRefused(553, b"bad sender", "bpp@example.com"),
    ):
        assert len(_wyslane_payloady(monkeypatch, filters, wyjatek)) == 1


def test_flaga_nie_wycisza_niczego_spoza_poczty(monkeypatch):
    filters = zbuduj_exception_level_filters(ignoruj_bledy_uwierzytelniania_smtp=True)

    assert len(_wyslane_payloady(monkeypatch, filters, ValueError("cokolwiek"))) == 1


def test_ustawienia_faktycznie_wpinaja_filtry_do_rollbara():
    """Sama funkcja nic nie da, jeśli nikt jej nie zawoła w ``settings``."""
    from django.conf import settings

    assert "exception_level_filters" in settings.ROLLBAR
    # W testach flaga jest wyłączona → żadnych wyciszeń. To jest też asercja
    # bezpieczeństwa: domyślna instalacja NIE gubi błędów.
    assert settings.ROLLBAR["exception_level_filters"] == []

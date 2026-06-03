"""Polskie tłumaczenia komunikatów błędów DjangoQL.

Tłumaczenia dostarcza fork ``djangoql-iplweb`` (zachowuje nazwę importu
``djangoql``), który owija komunikaty błędów parsera/leksera/schematu w
``gettext_lazy`` i dołącza katalog ``locale/pl/LC_MESSAGES/django.mo``.

Ten test pilnuje, że:
1. nadal jest zainstalowany fork z owinięciem ``gettext`` (a nie czysty
   upstream ``djangoql``, w którym komunikaty są zwykłymi stringami),
2. ``djangoql`` jest w ``INSTALLED_APPS`` — bez tego Django nie załaduje
   katalogu tłumaczeń pakietu,
3. komunikaty błędów faktycznie renderują się po polsku przy aktywnym
   języku ``pl`` (BPP działa z ``LANGUAGE_CODE = "pl"``).
"""

import pytest
from django.conf import settings
from django.utils.translation import gettext, override
from djangoql.exceptions import DjangoQLParserError
from djangoql.parser import DjangoQLParser


def test_djangoql_is_installed_app():
    """Bez tego wpisu Django nie wykryje katalogu locale/ pakietu djangoql."""
    assert "djangoql" in settings.INSTALLED_APPS


def test_djangoql_error_messages_are_translatable():
    """Upstream djangoql trzyma komunikaty jako gołe stringi — fork owija je
    w gettext_lazy, więc pod ``pl`` muszą się tłumaczyć."""
    with override("pl"):
        assert gettext("Unexpected end of input") == "Nieoczekiwany koniec wyrażenia"
        assert gettext("Illegal character %s") == "Niedozwolony znak %s"


def test_parser_error_renders_in_polish():
    """Realny błąd parsera DjangoQL przy aktywnym ``pl`` jest po polsku."""
    with override("pl"):
        with pytest.raises(DjangoQLParserError) as exc:
            DjangoQLParser().parse("nazwisko = ")
        assert "Nieoczekiwany koniec wyrażenia" in str(exc.value)


def test_parser_error_stays_english_under_en():
    """Sanity-check: pod ``en`` komunikat pozostaje oryginalny (angielski)."""
    with override("en"):
        with pytest.raises(DjangoQLParserError) as exc:
            DjangoQLParser().parse("nazwisko = ")
        assert "Unexpected end of input" in str(exc.value)

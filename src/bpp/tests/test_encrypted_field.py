import logging

import pytest
from cryptography.fernet import Fernet
from django.db import connection

from bpp import fields
from bpp.fields import EncryptedTextField, NieodszyfrowanaWartosc


@pytest.fixture(autouse=True)
def czysty_rejestr_zgloszonych():
    # Stan modułowy (ostrzeżenie raz na proces) — testy nie mogą zależeć
    # od kolejności uruchomienia.
    fields._zgloszone_nieodszyfrowalne.clear()
    yield
    fields._zgloszone_nieodszyfrowalne.clear()


@pytest.fixture
def fernet_key(settings):
    settings.FIELD_ENCRYPTION_KEY = ""
    settings.DSPACE_CREDENTIALS_KEY = Fernet.generate_key().decode()
    return settings.DSPACE_CREDENTIALS_KEY


def test_roundtrip_in_python(fernet_key):
    f = EncryptedTextField()
    stored = f.get_prep_value("tajne-haslo")
    assert stored != "tajne-haslo"  # zaszyfrowane
    back = f.from_db_value(stored, None, connection)
    assert back == "tajne-haslo"


def test_empty_passes_through(fernet_key):
    f = EncryptedTextField()
    assert f.get_prep_value("") == ""
    assert f.get_prep_value(None) is None


def test_each_encryption_differs(fernet_key):
    f = EncryptedTextField()
    assert f.get_prep_value("x") != f.get_prep_value("x")  # losowy IV


def test_from_db_value_degraduje_przy_zlym_kluczu(fernet_key):
    f = EncryptedTextField()
    stored = f.get_prep_value("sekret")  # zaszyfrowane kluczem A

    # podmień klucz na inny (B) — szyfrogram A staje się nieodszyfrowalny
    from cryptography.fernet import Fernet
    from django.test import override_settings

    with override_settings(DSPACE_CREDENTIALS_KEY=Fernet.generate_key().decode()):
        assert f.from_db_value(stored, None, connection) == ""


def _ostrzezenia(caplog):
    return [
        r
        for r in caplog.records
        if r.name == "bpp.fields" and r.levelno == logging.WARNING
    ]


@pytest.fixture
def nieodszyfrowalne(fernet_key, settings):
    """Dwa szyfrogramy zrobione kluczem, którego instancja już nie ma."""
    f = EncryptedTextField()
    szyfrogramy = f.get_prep_value("sekret-1"), f.get_prep_value("sekret-2")
    settings.DSPACE_CREDENTIALS_KEY = Fernet.generate_key().decode()
    return szyfrogramy


def test_nieodszyfrowalne_ostrzezenie_tylko_raz(nieodszyfrowalne, caplog):
    f = EncryptedTextField()
    szyfrogram, _ = nieodszyfrowalne

    with caplog.at_level(logging.DEBUG, logger="bpp.fields"):
        wyniki = [f.from_db_value(szyfrogram, None, connection) for _ in range(5)]

    # zwracana wartość bez zmian: pusta, ale pamięta szyfrogram
    for wynik in wyniki:
        assert wynik == ""
        assert isinstance(wynik, NieodszyfrowanaWartosc)
        assert wynik.szyfrogram == szyfrogram

    assert len(_ostrzezenia(caplog)) == 1
    powtorki = [
        r
        for r in caplog.records
        if r.name == "bpp.fields" and r.levelno == logging.DEBUG
    ]
    assert len(powtorki) == 4
    # ani szyfrogram, ani klucz nie trafiają do logu
    assert szyfrogram not in caplog.text


def test_nieodszyfrowalne_inna_wartosc_ma_wlasne_ostrzezenie(
    nieodszyfrowalne, caplog
):
    f = EncryptedTextField()
    pierwszy, drugi = nieodszyfrowalne

    with caplog.at_level(logging.DEBUG, logger="bpp.fields"):
        for szyfrogram in (pierwszy, drugi, pierwszy, drugi):
            assert f.from_db_value(szyfrogram, None, connection) == ""

    assert len(_ostrzezenia(caplog)) == 2


def test_nieodszyfrowalne_limit_rejestru(nieodszyfrowalne, caplog, monkeypatch):
    f = EncryptedTextField()
    pierwszy, drugi = nieodszyfrowalne
    monkeypatch.setattr(fields, "MAKS_ZGLOSZONYCH_NIEODSZYFROWALNYCH", 1)

    with caplog.at_level(logging.DEBUG, logger="bpp.fields"):
        f.from_db_value(pierwszy, None, connection)
        wynik = f.from_db_value(drugi, None, connection)

    # po osiągnięciu limitu rejestr nie rośnie, a nowe wartości idą na DEBUG
    assert wynik.szyfrogram == drugi
    assert len(_ostrzezenia(caplog)) == 1
    assert len(fields._zgloszone_nieodszyfrowalne) == 1

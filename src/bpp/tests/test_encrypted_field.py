import pytest
from cryptography.fernet import Fernet
from django.db import connection

from bpp.fields import EncryptedTextField


@pytest.fixture
def fernet_key(settings):
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

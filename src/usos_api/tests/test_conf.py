import pytest
from django.core.exceptions import ImproperlyConfigured

from usos_api.conf import buduj_klienta


def test_buduj_klienta_bierze_base_url_z_ustawien(settings):
    settings.USOS_API_BASE_URL = "https://usosapps.umlub.pl/"

    klient = buduj_klienta()

    assert klient.base_url == "https://usosapps.umlub.pl"


def test_buduj_klienta_argument_wygrywa_z_ustawieniami(settings):
    settings.USOS_API_BASE_URL = "https://usosapps.umlub.pl/"

    klient = buduj_klienta(base_url="https://usosapps.uw.edu.pl/")

    assert klient.base_url == "https://usosapps.uw.edu.pl"


def test_buduj_klienta_bez_base_url_zglasza_blad_konfiguracji(settings):
    settings.USOS_API_BASE_URL = None

    with pytest.raises(ImproperlyConfigured) as wyjatek:
        buduj_klienta()

    assert "USOS_API_BASE_URL" in str(wyjatek.value)


def test_buduj_klienta_bez_consumer_key_daje_klienta_anonimowego(settings):
    settings.USOS_API_BASE_URL = "https://usosapps.umlub.pl/"
    settings.USOS_API_CONSUMER_KEY = None

    assert buduj_klienta().anonimowy is True


def test_buduj_klienta_podaje_consumer_key_z_ustawien(settings):
    settings.USOS_API_BASE_URL = "https://usosapps.umlub.pl/"
    settings.USOS_API_CONSUMER_KEY = "KLUCZ"
    settings.USOS_API_CONSUMER_SECRET = "SEKRET"

    klient = buduj_klienta()

    assert klient.anonimowy is False
    assert klient.consumer_key == "KLUCZ"
    assert klient.consumer_secret == "SEKRET"

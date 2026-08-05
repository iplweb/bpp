"""Przełączniki konfiguracyjne REST API ``/api/v1/`` na obiekcie ``Uczelnia``.

Sześć pól: główny wyłącznik, ograniczenie do zalogowanych i cztery grupy
endpointów. Wszystkie defaulty zachowują dotychczasowe zachowanie — jedyne
domyślnie wyłączone to ograniczenie do zalogowanych.
"""

import pytest

from bpp.models import Uczelnia
from bpp.models.uczelnia import GrupaApiV1


def test_defaulty_zachowuja_obecne_zachowanie(uczelnia):
    """Wdrożenie sprzed tej zmiany nie traci żadnej funkcji."""
    assert uczelnia.api_v1_wlaczone is True
    assert uczelnia.api_v1_dane_bibliograficzne is True
    assert uczelnia.api_v1_wyszukiwanie is True
    assert uczelnia.api_v1_kafelki is True
    assert uczelnia.api_v1_narzedzia_redaktorskie is True


def test_tylko_zalogowani_domyslnie_wylaczone(uczelnia):
    """Jedyne pole, którego włączenie zmienia zachowanie — więc domyślnie
    wyłączone."""
    assert uczelnia.api_v1_tylko_zalogowani is False


@pytest.mark.parametrize("grupa", list(GrupaApiV1))
def test_kazda_grupa_ma_pole_na_uczelni(grupa):
    """Wartość enuma jest sufiksem nazwy pola (``api_v1_<value>``).

    Wiązanie idzie przez ``getattr``, więc nie ma kontroli statycznej —
    literówka w enumie wybuchłaby dopiero na produkcji, przy pierwszym
    żądaniu do danej grupy.
    """
    assert hasattr(Uczelnia, f"api_v1_{grupa.value}")


@pytest.mark.parametrize("grupa", list(GrupaApiV1))
def test_api_v1_grupa_wlaczona_czyta_wlasciwe_pole(uczelnia, grupa):
    assert uczelnia.api_v1_grupa_wlaczona(grupa) is True

    setattr(uczelnia, f"api_v1_{grupa.value}", False)
    assert uczelnia.api_v1_grupa_wlaczona(grupa) is False

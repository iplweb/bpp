"""Testy sekcji „Osiągnięcia (RAD-on)" na podstronie autora.

Sekcja jest tylko-szablonowa (dane pobiera klient JS na żywo z RAD-on). Partial
bramkuje się po ``autor.orcid`` i renderuje kontener ``[data-radon-osiagniecia]``
z ORCID-em, imieniem i nazwiskiem — resztę robi ``radon-profil.js`` w przeglądarce.
"""

import pytest
from model_bakery import baker

from bpp.models import Autor
from bpp.profil_autora import KLUCZ_RADON, KOLUMNA_LEWA
from bpp.profil_autora_dane import przygotuj_sekcje

pytestmark = pytest.mark.django_db


def test_radon_w_katalogu_lewej_kolumny():
    autor = baker.make(Autor)
    sekcje = przygotuj_sekcje(autor, uczelnia=None, request=None)
    klucze = [s["klucz"] for s in sekcje[KOLUMNA_LEWA]]
    assert KLUCZ_RADON in klucze


def test_kontener_renderuje_sie_gdy_autor_ma_orcid(client):
    autor = baker.make(
        Autor, imiona="Przemysław", nazwisko="Kowalczewski",
        orcid="0000-0002-0153-4624",
    )
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert "data-radon-osiagniecia" in tresc
    assert 'data-orcid="0000-0002-0153-4624"' in tresc
    assert 'data-nazwisko="Kowalczewski"' in tresc
    assert "informacje pobrane z RAD-on" in tresc


def test_brak_kontenera_gdy_autor_bez_orcid(client):
    autor = baker.make(Autor, nazwisko="Bezorcidowy", orcid="")
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert "data-radon-osiagniecia" not in tresc

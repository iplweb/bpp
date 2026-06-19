"""Testy historii zatrudnienia autora (metoda modelu + render partiala)."""

from datetime import date
from types import SimpleNamespace

import pytest
from django.template.loader import render_to_string
from model_bakery import baker

from bpp.models import Autor

pytestmark = pytest.mark.django_db


def test_historia_zatrudnienia_najnowsze_na_gorze(jednostka):
    from bpp.models import Autor_Jednostka

    autor = baker.make(Autor)
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2015, 1, 1),
    )
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2020, 1, 1),
        zakonczyl_prace=None,
    )

    historia = list(autor.historia_zatrudnienia())
    assert len(historia) == 2
    assert historia[0].rozpoczal_prace.year == 2020


def test_partial_pokazuje_obecnie_dla_otwartego_okresu():
    autor = SimpleNamespace(
        historia_zatrudnienia=lambda: [
            SimpleNamespace(
                jednostka=SimpleNamespace(nazwa="Katedra X", slug="katedra-x"),
                funkcja=SimpleNamespace(nazwa="Adiunkt"),
                rozpoczal_prace=date(2020, 1, 1),
                zakonczyl_prace=None,
            )
        ]
    )
    html = render_to_string(
        "browse/autor_sekcje/_historia_zatrudnienia.html", {"autor": autor}
    )
    assert "Katedra X" in html
    assert "obecnie" in html
    assert "Adiunkt" in html


def test_partial_pusty_gdy_brak_historii():
    autor = SimpleNamespace(historia_zatrudnienia=lambda: [])
    html = render_to_string(
        "browse/autor_sekcje/_historia_zatrudnienia.html", {"autor": autor}
    )
    assert "Historia zatrudnienia" not in html

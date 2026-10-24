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
    # Partial czyta listę z kontekstu `historia_zatrudnienia` (AutorView
    # podaje już przefiltrowany queryset), nie z metody autora.
    html = render_to_string(
        "browse/autor_sekcje/_historia_zatrudnienia.html",
        {
            "historia_zatrudnienia": [
                SimpleNamespace(
                    jednostka=SimpleNamespace(nazwa="Katedra X", slug="katedra-x"),
                    funkcja=SimpleNamespace(nazwa="Adiunkt"),
                    rozpoczal_prace=date(2020, 1, 1),
                    zakonczyl_prace=None,
                )
            ]
        },
    )
    assert "Katedra X" in html
    assert "obecnie" in html
    assert "Adiunkt" in html
    # Żadnych pytajników dla dat (filtrujemy wiersze bez daty w modelu).
    assert "?" not in html


def test_partial_pusty_gdy_brak_historii():
    html = render_to_string(
        "browse/autor_sekcje/_historia_zatrudnienia.html",
        {"historia_zatrudnienia": []},
    )
    assert "Historia zatrudnienia" not in html


def test_historia_pomija_wiersze_bez_daty_rozpoczecia(jednostka):
    from bpp.models import Autor_Jednostka

    autor = baker.make(Autor)
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2020, 1, 1),
    )
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=None,
    )
    historia = list(autor.historia_zatrudnienia())
    assert len(historia) == 1
    assert historia[0].rozpoczal_prace.year == 2020


def test_historia_pomija_obca_jednostke_gdy_znana_uczelnia(jednostka):
    from bpp.models import Autor_Jednostka, Jednostka

    uczelnia = jednostka.uczelnia
    obca = baker.make(
        Jednostka,
        uczelnia=uczelnia,
        wydzial=jednostka.wydzial,
        skupia_pracownikow=False,
    )
    uczelnia.obca_jednostka = obca
    uczelnia.save()

    autor = baker.make(Autor)
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2019, 1, 1),
    )
    baker.make(
        Autor_Jednostka, autor=autor, jednostka=obca, rozpoczal_prace=date(2018, 1, 1)
    )

    # Bez uczelni — nie filtrujemy obcej jednostki.
    assert len(list(autor.historia_zatrudnienia())) == 2
    # Z uczelnią — wiersz obcej jednostki znika.
    z_uczelnia = list(autor.historia_zatrudnienia(uczelnia))
    assert len(z_uczelnia) == 1
    assert z_uczelnia[0].jednostka_id == jednostka.pk

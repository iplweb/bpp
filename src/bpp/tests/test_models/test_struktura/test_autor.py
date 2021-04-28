# -*- encoding: utf-8 -*-
import pytest
from model_mommy import mommy

from bpp.models import (
    Autor,
    Jednostka,
    Typ_Odpowiedzialnosci,
    Tytul,
    Wydawnictwo_Ciagle,
)


@pytest.mark.django_db
def test_Autor_str(tytuly):
    x = Autor(
        nazwisko="Kowalski",
        imiona="Jan",
        tytul=Tytul.objects.first(),
        poprzednie_nazwiska="Budnik",
        pseudonim="Fafa",
    )
    assert str(x) == "Kowalski Jan (Budnik), dr (Fafa)"


@pytest.mark.django_db
def test_Autor_liczba_cytowan():
    Typ_Odpowiedzialnosci.objects.get_or_create(skrot="aut.", nazwa="autor")
    autor = mommy.make(Autor)
    jednostka = mommy.make(Jednostka, skupia_pracownikow=True)
    wc = mommy.make(Wydawnictwo_Ciagle, liczba_cytowan=200)
    wc.dodaj_autora(autor, jednostka, zapisany_jako="Jan K")

    j2 = mommy.make(Jednostka, skupia_pracownikow=False)
    wc2 = mommy.make(Wydawnictwo_Ciagle, liczba_cytowan=300)
    wc2.dodaj_autora(autor, j2, zapisany_jako="Jan K2", afiliuje=False)

    assert autor.liczba_cytowan() == 500


@pytest.mark.django_db
def test_liczba_cytowan_afiliowane():
    Typ_Odpowiedzialnosci.objects.get_or_create(skrot="aut.", nazwa="autor")
    autor = mommy.make(Autor)
    jednostka = mommy.make(Jednostka, skupia_pracownikow=True)
    wc = mommy.make(Wydawnictwo_Ciagle, liczba_cytowan=200)
    wc.dodaj_autora(autor, jednostka, zapisany_jako="Jan K")

    j2 = mommy.make(Jednostka, skupia_pracownikow=False)
    wc2 = mommy.make(Wydawnictwo_Ciagle, liczba_cytowan=300)
    wc2.dodaj_autora(autor, j2, zapisany_jako="Jan K2", afiliuje=False)

    assert autor.liczba_cytowan_afiliowane() == 200

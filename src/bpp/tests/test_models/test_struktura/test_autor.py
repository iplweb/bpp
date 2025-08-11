import pytest
from model_bakery import baker

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
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
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    wc = baker.make(Wydawnictwo_Ciagle, liczba_cytowan=200)
    wc.dodaj_autora(autor, jednostka, zapisany_jako="Jan K")

    j2 = baker.make(Jednostka, skupia_pracownikow=False)
    wc2 = baker.make(Wydawnictwo_Ciagle, liczba_cytowan=300)
    wc2.dodaj_autora(autor, j2, zapisany_jako="Jan K2", afiliuje=False)

    assert autor.liczba_cytowan() == 500


@pytest.mark.django_db
def test_liczba_cytowan_afiliowane():
    Typ_Odpowiedzialnosci.objects.get_or_create(skrot="aut.", nazwa="autor")
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    wc = baker.make(Wydawnictwo_Ciagle, liczba_cytowan=200)
    wc.dodaj_autora(autor, jednostka, zapisany_jako="Jan K")

    j2 = baker.make(Jednostka, skupia_pracownikow=False)
    wc2 = baker.make(Wydawnictwo_Ciagle, liczba_cytowan=300)
    wc2.dodaj_autora(autor, j2, zapisany_jako="Jan K2", afiliuje=False)

    assert autor.liczba_cytowan_afiliowane() == 200


@pytest.mark.django_db
def test_aktualna_dyscyplina(autor_z_dyscyplina, dyscyplina1):
    assert autor_z_dyscyplina.autor.aktualna_dyscyplina().pk == dyscyplina1.pk
    assert autor_z_dyscyplina.autor.aktualna_subdyscyplina() is None


@pytest.mark.django_db
def test_aktualna_subdyscyplina(autor_z_dyscyplina, dyscyplina2):
    ad = Autor_Dyscyplina.objects.get(autor=autor_z_dyscyplina.autor)
    ad.subdyscyplina_naukowa = dyscyplina2
    ad.save()

    assert autor_z_dyscyplina.autor.aktualna_subdyscyplina().pk == dyscyplina2.pk


@pytest.mark.django_db
def test_nieaktualna_dyscyplina(autor_jan_kowalski, dyscyplina1):
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=2000, dyscyplina_naukowa=dyscyplina1
    )

    assert autor_jan_kowalski.aktualna_dyscyplina() is None

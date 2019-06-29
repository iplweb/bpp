import pytest
from django.core.exceptions import ValidationError
from django.db import InternalError
from psycopg2._psycopg import DatabaseError

from bpp.models import Autor_Dyscyplina


def test_autor_dyscyplina_save_ta_sama(autor_jan_kowalski, dyscyplina1, dyscyplina2, rok):
    ad = Autor_Dyscyplina.objects.create(
        rok=rok,
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2
    )

    ad.subdyscyplina_naukowa = dyscyplina1

    with pytest.raises(ValidationError):
        ad.clean()


def test_autor_dyscyplina_procent_ponad(autor_jan_kowalski, dyscyplina1, dyscyplina2, rok):
    ad = Autor_Dyscyplina.objects.create(
        rok=rok,
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        procent_dyscypliny=100,
        subdyscyplina_naukowa=dyscyplina2,
        procent_subdyscypliny=1)

    with pytest.raises(ValidationError):
        ad.clean()


def test_autor_dyscyplina_change_trigger_single(autor_jan_kowalski, jednostka, dyscyplina1, dyscyplina2, dyscyplina3,
                                                rok, wydawnictwo_ciagle, wydawnictwo_zwarte, typy_odpowiedzialnosci):
    """Sprawdź, czy zmiana przypisania Autor_Dyscyplina na dany rok pociągnie zmianę w wydawnictwach 
    ciągłych, zwartych i patentach. Skasowanie przypisania z kolei ustawi przypisanie na NULL. """

    ad = Autor_Dyscyplina.objects.create(
        rok=rok,
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2
    )

    wydawnictwo_zwarte.rok = rok + 50
    wydawnictwo_zwarte.save()

    wza = wydawnictwo_zwarte.dodaj_autora(
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        zapisany_jako='Tu sie nie zmieni bo bedzie inny rok',
        dyscyplina_naukowa=dyscyplina1
    )

    wca = wydawnictwo_ciagle.dodaj_autora(
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        zapisany_jako="J. Kowalski",
        dyscyplina_naukowa=dyscyplina1
    )

    ad.dyscyplina_naukowa = dyscyplina3
    ad.save()

    wca.refresh_from_db()
    assert wca.dyscyplina_naukowa == dyscyplina3

    wza.refresh_from_db()
    assert wza.dyscyplina_naukowa == dyscyplina1

    ad.delete()

    wca.refresh_from_db()
    assert wca.dyscyplina_naukowa == None

    wza.refresh_from_db()
    assert wza.dyscyplina_naukowa == dyscyplina1


def test_autor_dyscyplina_change_trigger_double(autor_jan_kowalski, jednostka, dyscyplina1, dyscyplina2, rok,
                                                wydawnictwo_ciagle, wydawnictwo_zwarte, patent, typy_odpowiedzialnosci):
    """Sprawdź, czy zmiana przypisania Autor_Dyscyplina na dany rok pociągnie zmianę w wydawnictwach
    ciągłych, zwartych i patentach. Skasowanie przypisania z kolei ustawi przypisanie na NULL. """

    ad = Autor_Dyscyplina.objects.create(
        rok=rok,
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2
    )

    wca = wydawnictwo_ciagle.dodaj_autora(
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        zapisany_jako="J. Kowalski",
        dyscyplina_naukowa=dyscyplina1
    )

    wza = wydawnictwo_zwarte.dodaj_autora(
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        zapisany_jako="Kowalski Jan",
        dyscyplina_naukowa=dyscyplina2
    )

    ad.dyscyplina_naukowa = dyscyplina2
    ad.subdyscyplina_naukowa = dyscyplina1
    ad.save()

    wca.refresh_from_db()
    assert wca.dyscyplina_naukowa == dyscyplina2
    wza.refresh_from_db()
    assert wza.dyscyplina_naukowa == dyscyplina1


def test_autor_dyscyplina_taka_sama_trigger(autor_jan_kowalski, dyscyplina1, rok):
    """Sprawdź funkcjonowanie triggera bazodanowego przy wrzuceniu tej samej
    dyscypliny do Autor_Dyscyplina (czyli nie 'save' tylko testujemy trigger
    po stronie bazy danych). """

    with pytest.raises(InternalError):
        Autor_Dyscyplina.objects.create(
            rok=rok,
            autor=autor_jan_kowalski,
            dyscyplina_naukowa=dyscyplina1,
            subdyscyplina_naukowa=dyscyplina1
        )


def test_autor_dyscyplina_zmiana_roku(autor_jan_kowalski, dyscyplina1, rok):
    """Sprawdź funkcjonowanie triggera bazodanowego przy wrzuceniu tej samej
    dyscypliny do Autor_Dyscyplina (czyli nie 'save' tylko testujemy trigger
    po stronie bazy danych). """

    ad = Autor_Dyscyplina.objects.create(
        rok=rok,
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
    )

    ad.rok = rok + 50
    with pytest.raises(InternalError):
        ad.save()


def test_autor_dyscyplina_zmiana_autora(autor_jan_kowalski, autor_jan_nowak, dyscyplina1, rok):
    ad = Autor_Dyscyplina.objects.create(
        rok=rok,
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
    )

    ad.autor = autor_jan_nowak
    with pytest.raises(InternalError):
        ad.save()

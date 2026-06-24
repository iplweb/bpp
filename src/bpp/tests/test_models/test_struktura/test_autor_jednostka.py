from datetime import date, datetime, timedelta

import pytest
from django.db import IntegrityError, InternalError, OperationalError, transaction
from model_bakery import baker

from bpp.models.autor import Autor_Jednostka


@pytest.mark.django_db(transaction=True)
def test_autor_jednostka_zamiana_podstawowego_miejsca_w_jednej_transakcji(
    autor_jan_kowalski, jednostka, druga_jednostka
):
    """Przełączenie podstawowego miejsca pracy z jednostki A na B w obrębie
    JEDNEJ transakcji musi się udać, nawet jeśli nowe podstawowe miejsce (B)
    jest zapisywane PRZED odznaczeniem starego (A) — przejściowo istnieją
    wtedy dwa rekordy z podstawowe_miejsce_pracy=True. Niezmiennik
    egzekwujemy dopiero przy COMMIT (deferred constraint trigger)."""
    a = baker.make(
        Autor_Jednostka,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        podstawowe_miejsce_pracy=True,
    )
    b = baker.make(
        Autor_Jednostka,
        autor=autor_jan_kowalski,
        jednostka=druga_jednostka,
    )

    with transaction.atomic():
        # Kolejność "najpierw zaznacz nowe" — to ona wysadzała immediate index.
        b.podstawowe_miejsce_pracy = True
        b.save()
        a.podstawowe_miejsce_pracy = False
        a.save()

    assert (
        Autor_Jednostka.objects.filter(
            autor=autor_jan_kowalski, podstawowe_miejsce_pracy=True
        ).count()
        == 1
    )
    b.refresh_from_db()
    assert b.podstawowe_miejsce_pracy is True


@pytest.mark.django_db(transaction=True)
def test_autor_jednostka_dwa_podstawowe_miejsca_pracy_odrzucone(
    autor_jan_kowalski, jednostka, druga_jednostka
):
    """Stan KOŃCOWY z dwoma podstawowymi miejscami pracy nadal jest błędem."""
    baker.make(
        Autor_Jednostka,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        podstawowe_miejsce_pracy=True,
    )
    with pytest.raises(IntegrityError):
        baker.make(
            Autor_Jednostka,
            autor=autor_jan_kowalski,
            jednostka=druga_jednostka,
            podstawowe_miejsce_pracy=True,
        )


@pytest.mark.django_db
def test_autor_jednostka_trigger_nie_mozna_zmienic_id_autora(
    autor_jan_kowalski, autor_jan_nowak, jednostka
):
    aj = baker.make(Autor_Jednostka, autor=autor_jan_kowalski, jednostka=jednostka)
    aj.autor = autor_jan_nowak
    with pytest.raises((OperationalError, InternalError)):
        aj.save()


@pytest.mark.django_db
def test_autor_jednostka_trigger_nie_mozna_daty_w_przyszlosci(
    autor_jan_kowalski, jednostka
):
    aj = baker.make(Autor_Jednostka, autor=autor_jan_kowalski, jednostka=jednostka)
    aj.zakonczyl_prace = date.today()
    with pytest.raises(IntegrityError):
        aj.save()


@pytest.mark.django_db
def test_autor_jednostka_trigger_ustaw_aktualna_jednostke_1(
    autor_jan_kowalski, jednostka
):
    aj = baker.make(Autor_Jednostka, autor=autor_jan_kowalski, jednostka=jednostka)
    autor_jan_kowalski.refresh_from_db()
    assert autor_jan_kowalski.aktualna_jednostka == jednostka

    aj.zakonczyl_prace = date.today() - timedelta(days=5)
    aj.save()
    autor_jan_kowalski.refresh_from_db()
    assert autor_jan_kowalski.aktualna_jednostka is None

    aj.delete()
    autor_jan_kowalski.refresh_from_db()
    assert autor_jan_kowalski.aktualna_jednostka is None


@pytest.mark.django_db
def test_autor_jednostka_trigger_ustaw_aktualna_jednostke_2(
    autor_jan_kowalski, jednostka, druga_jednostka
):
    baker.make(
        Autor_Jednostka,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        rozpoczal_prace=date(2012, 1, 1),
        zakonczyl_prace=date(2012, 2, 1),
    )
    baker.make(
        Autor_Jednostka,
        autor=autor_jan_kowalski,
        jednostka=druga_jednostka,
        rozpoczal_prace=date(2012, 1, 1),
        zakonczyl_prace=date(2012, 2, 2),
    )
    autor_jan_kowalski.refresh_from_db()

    assert autor_jan_kowalski.aktualna_jednostka is None


@pytest.mark.django_db
def test_autor_jednostka_trigger_ustaw_aktualna_jednostke_3(
    autor_jan_kowalski, jednostka, druga_jednostka
):
    baker.make(Autor_Jednostka, autor=autor_jan_kowalski, jednostka=druga_jednostka)
    baker.make(Autor_Jednostka, autor=autor_jan_kowalski, jednostka=jednostka)

    # przy dwóch przypisaniach aktualne ma byc to drugie (późniejsze) przypisane
    # sprawdzane jest to po ID w bazie

    autor_jan_kowalski.refresh_from_db()

    assert autor_jan_kowalski.aktualna_jednostka == jednostka


@pytest.mark.django_db
def test_autor_jednostka_trigger_ustaw_aktualna_jednostke_podstawowe_miejsce_pracy(
    autor_jan_kowalski, jednostka, druga_jednostka
):
    baker.make(
        Autor_Jednostka,
        autor=autor_jan_kowalski,
        jednostka=druga_jednostka,
        podstawowe_miejsce_pracy=True,
    )
    baker.make(Autor_Jednostka, autor=autor_jan_kowalski, jednostka=jednostka)

    # aktualne ma byc to miejsce, ktore ma 'podstawowe miejsce pracy' True

    autor_jan_kowalski.refresh_from_db()

    assert autor_jan_kowalski.aktualna_jednostka == druga_jednostka


@pytest.mark.django_db
def test_autor_jednostka_trigger_odepnij_wszystkie_jednostki(
    autor_jan_kowalski, jednostka
):
    baker.make(
        Autor_Jednostka,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        podstawowe_miejsce_pracy=True,
        zakonczyl_prace=datetime.now().date() - timedelta(days=3),
    )

    autor_jan_kowalski.refresh_from_db()

    # Po odpięciu wszystkiego jednostka ma być None
    assert autor_jan_kowalski.aktualna_jednostka is None

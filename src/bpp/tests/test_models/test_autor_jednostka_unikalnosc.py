"""Unikalność powiązania autor-jednostka przy pustym ``rozpoczal_prace``.

``Autor_Jednostka.Meta.unique_together = [("autor", "jednostka",
"rozpoczal_prace")]`` deklaruje niezmiennik „jedno powiązanie na trójkę",
ale w PostgreSQL NULL-e w indeksie unikalnym są wzajemnie rozróżnialne —
wiersze z ``rozpoczal_prace IS NULL`` nie były więc niczym chronione.

Ścieżka ``Wydawnictwo_*_Autor.save()`` (najgorętsza w systemie) robi
check-then-create dokładnie na parze ``(autor, jednostka)`` z NULL-owym
``rozpoczal_prace``, więc dwa równoległe zapisy produkowały duplikaty.
"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.db import IntegrityError, transaction
from model_bakery import baker

from bpp.models import Autor, Jednostka
from bpp.models.autor import Autor_Jednostka


@pytest.mark.django_db
def test_autor_jednostka_bez_daty_rozpoczecia_nie_moze_sie_dublowac():
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka)

    assert (
        Autor_Jednostka.objects.filter(
            autor=autor, jednostka=jednostka, rozpoczal_prace=None
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_wiele_okresow_zatrudnienia_z_datami_nadal_dozwolone():
    """Constraint jest częściowy — nie rusza legalnych okresów zatrudnienia."""
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2012, 12, 31),
    )
    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2015, 1, 1),
        zakonczyl_prace=date(2018, 12, 31),
    )
    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2020, 1, 1),
    )

    assert Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).count() == 3


@pytest.mark.django_db
def test_wiersz_bez_daty_obok_okresow_z_datami_jest_dozwolony():
    """Jeden wiersz „bez dat" współistnieje z wierszami datowanymi."""
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2012, 12, 31),
    )
    Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka)

    assert Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).count() == 2


@pytest.mark.django_db
def test_zapis_autorstwa_przezywa_wyscig_o_powiazanie(
    wydawnictwo_ciagle, autor_jan_nowak, jednostka, typy_odpowiedzialnosci
):
    """Constraint nie moze wywalac zapisu autorstwa przy wyscigu.

    Symulujemy sytuacje, w ktorej rownolegla transakcja utworzyla powiazanie
    w okienku miedzy ``exists()`` a ``create()``: pierwsze sprawdzenie zwraca
    "nie ma", a ``create()`` konczy sie ``IntegrityError``. Zapis autorstwa ma
    to przezyc, bo stan docelowy (powiazanie istnieje) jest osiagniety.
    """
    Autor_Jednostka.objects.create(autor=autor_jan_nowak, jednostka=jednostka)

    with patch.object(
        Autor_Jednostka.objects,
        "create",
        side_effect=IntegrityError("duplicate key value violates unique constraint"),
    ):
        with patch.object(
            Autor_Jednostka.objects,
            "filter",
            side_effect=[
                SimpleNamespace(exists=lambda: False),  # wyscig: "jeszcze nie ma"
                SimpleNamespace(exists=lambda: True),  # po IntegrityError: "juz jest"
            ],
        ):
            wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)

    assert (
        Autor_Jednostka.objects.filter(
            autor=autor_jan_nowak, jednostka=jednostka
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_zapis_autorstwa_nie_polyka_obcego_integrityerror(
    wydawnictwo_ciagle, autor_jan_nowak, jednostka, typy_odpowiedzialnosci
):
    """IntegrityError z INNEGO powodu niz wyscig ma polecec dalej."""
    with patch.object(
        Autor_Jednostka.objects,
        "create",
        side_effect=IntegrityError("insert or update violates foreign key constraint"),
    ):
        with pytest.raises(IntegrityError):
            wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)


@pytest.mark.django_db
def test_dodaj_jednostke_bez_roku_dwa_razy_nie_lamie_transakcji():
    """``Autor.dodaj_jednostke`` bez ``rok`` tworzy wiersz z pusta data.

    Drugie wywolanie trafia teraz w constraint. Istniejacy tam
    ``except IntegrityError: return`` musi zadzialac, a transakcja pozostac
    uzywalna (savepoint) — inaczej kazdy dalszy SELECT rzucilby
    ``TransactionManagementError``.
    """
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    assert autor.dodaj_jednostke(jednostka) is not None
    assert autor.dodaj_jednostke(jednostka) is None

    # Transakcja zyje — kolejne zapytanie sie wykonuje:
    assert (
        Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).count() == 1
    )

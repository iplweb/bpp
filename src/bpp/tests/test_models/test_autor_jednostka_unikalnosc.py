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


@pytest.mark.django_db
def test_dodaj_jednostke_nie_polyka_obcego_integrityerror():
    """Genuine IntegrityError (nie wyscig) w ``dodaj_jednostke`` PROPAGUJE.

    Do tej gałęzi wpadał każdy ``IntegrityError`` — łącznie z realnym błędem
    danych (zerwany FK, naruszony datowany unique_together), który cichłby
    jako ``return None`` ignorowane przez importery. Symulujemy ``create()``
    rzucający IntegrityError, przy czym powiazanie (autor, jednostka) bez daty
    NADAL nie istnieje — to znaczy, że nie był to wyścig i wyjątek musi
    polecieć dalej, a nie zostać połknięty.
    """
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    with patch.object(
        Autor_Jednostka.objects,
        "create",
        side_effect=IntegrityError(
            "insert or update violates foreign key constraint"
        ),
    ):
        with pytest.raises(IntegrityError):
            autor.dodaj_jednostke(jednostka)

    # Nie powstal zaden wiersz — potwierdza, ze to byl genuine blad, nie wyscig:
    assert not Autor_Jednostka.objects.filter(
        autor=autor, jednostka=jednostka
    ).exists()


@pytest.mark.django_db
def test_dodaj_jednostke_z_rokiem_nie_polyka_obcego_integrityerror():
    """Genuine IntegrityError na sciezce DATOWANEJ (``rok=X``) PROPAGUJE.

    Symetryczny do wariantu bez roku: ``create()`` rzuca IntegrityError, a
    wiersz ``(autor, jednostka, rozpoczal_prace=date(X, 1, 1))`` nadal nie
    istnieje — to nie wyscig, wiec wyjatek musi poleciec dalej, a nie zostac
    polkniety jako cichy ``return None``.
    """
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    with patch.object(
        Autor_Jednostka.objects,
        "create",
        side_effect=IntegrityError(
            "insert or update violates foreign key constraint"
        ),
    ):
        with pytest.raises(IntegrityError):
            autor.dodaj_jednostke(jednostka, rok=2020)

    assert not Autor_Jednostka.objects.filter(
        autor=autor, jednostka=jednostka
    ).exists()


@pytest.mark.django_db
def test_dodaj_jednostke_z_rokiem_wchlania_wyscig_na_datowanej_parze():
    """Wyscig na datowanej parze -> ``return None`` (bez re-raise).

    Regresja naprawiana tu: post-check pytal na sztywno o
    ``rozpoczal_prace__isnull=True``, wiec dla ``rok=X`` (wiersz DATOWANY)
    nigdy nie rozpoznawal prawdziwego wyscigu i re-raise'owal go jako 500.

    Wiersz ``(autor, jednostka, rozpoczal_prace=date(2020, 1, 1))`` juz
    istnieje (z ``zakonczyl_prace=None``, zeby interwalowy ``czy_juz_istnieje``
    go NIE zlapal i doszlo do ``create()``). ``create()`` rzuca IntegrityError,
    a post-check znajduje dokladnie te trojke -> ``return None``.
    """
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2020, 1, 1),
        zakonczyl_prace=None,
    )

    with patch.object(
        Autor_Jednostka.objects,
        "create",
        side_effect=IntegrityError("duplicate key value violates unique constraint"),
    ):
        assert autor.dodaj_jednostke(jednostka, rok=2020) is None

    # Nadal jeden wiersz — cichy no-op, bez propagacji:
    assert (
        Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).count() == 1
    )


@pytest.mark.django_db
def test_nakladajace_sie_okresy_zatrudnienia_sa_zabronione():
    """ExclusionConstraint: dwa DATOWANE okresy nie moga sie nakladac.

    Pilnuje ``bpp_autor_jednostka_okresy_bez_nakladan`` (0474). Pierwszy okres
    [2010..2015], drugi zaczyna sie w srodku [2013..2018] -> nakladaja sie ->
    ``IntegrityError``.
    """
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2015, 12, 31),
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Autor_Jednostka.objects.create(
                autor=autor,
                jednostka=jednostka,
                rozpoczal_prace=date(2013, 1, 1),
                zakonczyl_prace=date(2018, 12, 31),
            )


@pytest.mark.django_db
def test_okresy_dzielace_skrajny_dzien_sie_nakladaja():
    """Granice '[]' inkluzywne: wspolny skrajny dzien = NAKLADANIE.

    [2010..2012-12-31] i [2012-12-31..2015] dziela dzien 2012-12-31. Bo obie
    granice sa domkniete, ten dzien nalezy do obu -> ``IntegrityError``.
    """
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2012, 12, 31),
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Autor_Jednostka.objects.create(
                autor=autor,
                jednostka=jednostka,
                rozpoczal_prace=date(2012, 12, 31),
                zakonczyl_prace=date(2015, 12, 31),
            )


@pytest.mark.django_db
def test_przylegajace_okresy_sa_dozwolone():
    """Przyleganie (koniec + 1 dzien = nastepny start) NIE jest nakladaniem.

    [2010..2012-12-31] i [2013-01-01..2015] stykaja sie bez wspolnego dnia ->
    obie granice '[]' sie nie przecinaja -> zapis PRZECHODZI. Nie wolno nam
    falszywie blokowac legalnej, ciaglej historii zatrudnienia.
    """
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
        rozpoczal_prace=date(2013, 1, 1),
        zakonczyl_prace=date(2015, 12, 31),
    )

    assert Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).count() == 2


@pytest.mark.django_db
def test_rozlaczne_okresy_sa_dozwolone():
    """Okresy z luka miedzy nimi PRZECHODZA (brak nakladania)."""
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

    assert Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).count() == 2


@pytest.mark.django_db
def test_otwarty_koniec_nakladajacy_pozniejszy_okres_jest_zabroniony():
    """Otwarty koniec (``zakonczyl_prace`` NULL) = zakres [start, nieskonczonosc).

    Autor z otwartym okresem [2010..) i drugi datowany okres [2015..2016]
    zawarty w tamtym -> nakladaja sie -> ``IntegrityError``. Potwierdza, ze
    ``daterange(start, NULL, '[]')`` obejmuje wszystko po ``start``.
    """
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=None,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Autor_Jednostka.objects.create(
                autor=autor,
                jednostka=jednostka,
                rozpoczal_prace=date(2015, 1, 1),
                zakonczyl_prace=date(2016, 12, 31),
            )


@pytest.mark.django_db
def test_otwarty_koniec_przylegajacy_wczesniejszy_okres_jest_dozwolony():
    """Zamkniety okres tuz przed otwartym (koniec + 1 = start) PRZECHODZI."""
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2013, 1, 1),
        zakonczyl_prace=None,
    )
    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2012, 12, 31),
    )

    assert Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).count() == 2


@pytest.mark.django_db
def test_dodaj_jednostke_wchlania_wyscig_przedzialowy_pokrywajacy():
    """Wyscig na sciezce PRZEDZIALOWEJ: pokrywajacy okres -> zwroc go.

    Rownolegla transakcja utworzyla okres [2019..2021] POKRYWAJACY zadany rok
    2020 (o INNYM ``rozpoczal_prace``) DOPIERO w okienku miedzy ``exists()`` a
    ``create()``, wiec nasz ``create()`` laduje na ExclusionConstraincie
    'bpp_autor_jednostka_okresy_bez_nakladan'. Post-check pytajacy o dokladny
    start (2020-01-01) by go NIE zlapal, bo tamten wiersz ma inny start —
    dlatego ``dodaj_jednostke`` najpierw pyta o wiersz POKRYWAJACY zadany zakres
    i zwraca go (stan docelowy osiagniety), zamiast re-raise'owac jako 500.

    Wyscig symulujemy patchem ``filter`` (jak
    ``test_zapis_autorstwa_przezywa_wyscig``): pierwszy ``filter`` — wejsciowy
    ``exists()`` — mowi "nie ma", a ``filter`` w bloku ``except`` zwraca
    pokrywajacy wiersz. Predykat wejsciowy i przedzialowy sa IDENTYCZNE, wiec
    tylko taki mock oddaje wyscig (real DB nie da roznicy).
    """
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    pokrywajacy = Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2019, 1, 1),
        zakonczyl_prace=date(2021, 12, 31),
    )

    with patch.object(
        Autor_Jednostka.objects,
        "create",
        side_effect=IntegrityError(
            "conflicting key value violates exclusion constraint"
        ),
    ):
        with patch.object(
            Autor_Jednostka.objects,
            "filter",
            side_effect=[
                SimpleNamespace(exists=lambda: False),  # wejscie: "jeszcze nie ma"
                SimpleNamespace(first=lambda: pokrywajacy),  # except: pokrywajacy
            ],
        ):
            wynik = autor.dodaj_jednostke(jednostka, rok=2020)

    assert wynik == pokrywajacy


@pytest.mark.django_db
def test_filter_rozpoczal_prace_none_generuje_is_null():
    """``filter(rozpoczal_prace=None)`` musi kompilowac sie do ``IS NULL``.

    Od tego zalezy poprawnosc post-checku dla sciezki bez roku (``start_pracy``
    = None): gdyby Django wygenerowalo ``= NULL``, warunek nigdy nie zlapalby
    NULL-owego wyscigu. Weryfikujemy to na wygenerowanym SQL.
    """
    sql = str(Autor_Jednostka.objects.filter(rozpoczal_prace=None).query)
    assert "IS NULL" in sql
    assert "= NULL" not in sql

import os

import pytest
from django.core.files.base import ContentFile
from django.db import transaction

from bpp.models import Autor_Dyscyplina, Dyscyplina_Naukowa
from import_dyscyplin.models import (
    Import_Dyscyplin,
    Import_Dyscyplin_Row,
    Kolumna,
    guess_rodzaj,
)


def test_guess_rodzaj():
    assert guess_rodzaj("nazwisko") == Kolumna.RODZAJ.NAZWISKO
    assert guess_rodzaj("kopara") == Kolumna.RODZAJ.POMIJAJ
    assert guess_rodzaj("lp") == Kolumna.RODZAJ.POMIJAJ


def test_Import_Dyscyplin_post_delete_handler(
    test1_xlsx, normal_django_user, transactional_db
):
    path = None
    with transaction.atomic():
        i = Import_Dyscyplin.objects.create(
            owner=normal_django_user,
        )

        i.plik.save("test1.xls", ContentFile(open(test1_xlsx, "rb").read()))
        path = i.plik.path
        i.delete()

    assert not os.path.exists(path)


@pytest.fixture
def testowe_dyscypliny():
    Dyscyplina_Naukowa.objects.create(nazwa="Testowa", kod="3.2", widoczna=False)

    Dyscyplina_Naukowa.objects.create(nazwa="Jakaś", kod="3.2.1", widoczna=False)


@pytest.fixture
def id_row_1(import_dyscyplin, autor_jan_nowak):
    return Import_Dyscyplin_Row.objects.create(
        parent=import_dyscyplin,
        row_no=1,
        original={},
        dyscyplina="Testowa",
        kod_dyscypliny="3.2",
        subdyscyplina="Jakaś",
        kod_subdyscypliny="3.2.1",
        autor=autor_jan_nowak,
    )


@pytest.fixture
def id_row_2(import_dyscyplin, autor_jan_nowak):
    return Import_Dyscyplin_Row.objects.create(
        parent=import_dyscyplin,
        row_no=1,
        original={},
        dyscyplina="Testowa",
        kod_dyscypliny="3.2",
        subdyscyplina=None,
        kod_subdyscypliny=None,
        autor=autor_jan_nowak,
    )


def test_Import_Dyscyplin_integruj_dyscypliny_pusta_baza(import_dyscyplin, id_row_1):
    import_dyscyplin.integruj_dyscypliny()

    assert Dyscyplina_Naukowa.objects.all().count() == 2
    Dyscyplina_Naukowa.objects.get(nazwa="Testowa")

    for elem in Dyscyplina_Naukowa.objects.all():
        assert elem.widoczna


def test_Import_Dyscyplin_integruj_dyscypliny_ta_sama_nazwa_inny_kod(
    import_dyscyplin, id_row_1
):
    Dyscyplina_Naukowa.objects.create(nazwa="Testowa", kod="0.0")

    import_dyscyplin.integruj_dyscypliny()

    assert Dyscyplina_Naukowa.objects.all().count() == 1

    id_row_1.refresh_from_db()
    assert id_row_1.stan == Import_Dyscyplin_Row.STAN.BLEDNY


def test_Import_Dyscyplin_integruj_dyscypliny_ta_sama_nazwa_inny_kod_sub(
    import_dyscyplin, id_row_1
):
    Dyscyplina_Naukowa.objects.create(nazwa="Jakaś", kod="5.3")

    import_dyscyplin.integruj_dyscypliny()

    assert Dyscyplina_Naukowa.objects.all().count() == 2

    id_row_1.refresh_from_db()
    assert id_row_1.stan == Import_Dyscyplin_Row.STAN.BLEDNY


def test_Import_Dyscyplin_integruj_dyscypliny_ukryj_nieuzywane_brak_dyscyplin(
    import_dyscyplin, id_row_1
):
    import_dyscyplin.integruj_dyscypliny()
    Autor_Dyscyplina.objects.ukryj_nieuzywane()
    assert Dyscyplina_Naukowa.objects.all().count() == 2
    for elem in Dyscyplina_Naukowa.objects.all():
        assert not elem.widoczna


def test_Import_Dyscyplin_integruj_dyscypliny_ukryj_nieuzywane_uzywana_nadrzedna(
    import_dyscyplin, id_row_2, autor_jan_nowak, testowe_dyscypliny
):
    assert Autor_Dyscyplina.objects.count() == 0

    import_dyscyplin.integruj_dyscypliny()
    import_dyscyplin._integruj_wiersze()

    assert Autor_Dyscyplina.objects.count() == 1
    assert Dyscyplina_Naukowa.objects.get(nazwa="Testowa").widoczna
    assert not Dyscyplina_Naukowa.objects.get(nazwa="Jakaś").widoczna


def test_Import_Dyscyplin_integruj_dyscypliny_ukryj_nieuzywane_uzywana_podrzedna(
    import_dyscyplin, id_row_1, testowe_dyscypliny
):
    assert Autor_Dyscyplina.objects.count() == 0

    import_dyscyplin.integruj_dyscypliny()
    import_dyscyplin._integruj_wiersze()
    assert Autor_Dyscyplina.objects.count() == 1

    assert Dyscyplina_Naukowa.objects.get(nazwa="Testowa").widoczna
    assert Dyscyplina_Naukowa.objects.get(nazwa="Jakaś").widoczna


def test_Import_Dyscyplin_sprawdz_czy_poprawne(
    import_dyscyplin, autor_jan_nowak, id_row_1
):
    id_row_2 = Import_Dyscyplin_Row.objects.create(
        parent=import_dyscyplin,
        row_no=1,
        original={},
        dyscyplina="Testowa",
        kod_dyscypliny="3.2",
        subdyscyplina="Jakaś",
        kod_subdyscypliny="3.2.1",
        autor=autor_jan_nowak,
    )

    import_dyscyplin.integruj_dyscypliny()

    assert id_row_1 in list(import_dyscyplin.poprawne_wiersze_do_integracji())

    import_dyscyplin.sprawdz_czy_poprawne()

    for elem in id_row_1, id_row_2:
        elem.refresh_from_db()
        assert elem.stan == Import_Dyscyplin_Row.STAN.BLEDNY


def test_Import_Dyscyplin_integruj_dyscypliny_zmiana_dyscypliny(
    autor_jan_nowak, rok, import_dyscyplin, id_row_1, testowe_dyscypliny
):
    # Zróbmy tak, że autor ma przypisanie za dany rok dla dyscypliny
    # innej, niż w wierszu importu. W wierszu id_row_1 idzie 'Testowa'
    # jako dyscyplina...
    ad = Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        rok=rok,
        dyscyplina_naukowa=Dyscyplina_Naukowa.objects.get(nazwa="Jakaś"),
    )

    import_dyscyplin.integruj_dyscypliny()
    import_dyscyplin._integruj_wiersze()

    ad.refresh_from_db()
    assert ad.dyscyplina_naukowa.nazwa == "Testowa"


def test_Import_Dyscyplin_Row_serialize_dict():
    x = Import_Dyscyplin_Row(nazwisko="foo", imiona="bar", original={})
    assert x.serialize_dict()["nazwisko"] == "foo"

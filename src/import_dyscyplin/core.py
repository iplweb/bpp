from hashlib import md5

import xlrd
from django.db import transaction
from django.db.models import Q
from xlrd import XLRDError

from bpp.models import Wydzial, Jednostka, Autor
from import_dyscyplin.exceptions import BadNoOfSheetsException, HeaderNotFoundException, ImproperFileException
from import_dyscyplin.models import Import_Dyscyplin_Row

naglowek = [
    "lp", "tytuł/stopień", "nazwisko", "imię", "pesel",
    "nazwa jednostki", "wydział",
    "dyscyplina", "kod dyscypliny",
    "subdyscyplina", "kod subdyscypliny"
]


def matchuj_wydzial(nazwa):
    try:
        return Wydzial.objects.get(nazwa__iexact=nazwa.strip())
    except Wydzial.DoesNotExist:
        pass


def matchuj_jednostke(nazwa):
    try:
        return Jednostka.objects.get(
            Q(nazwa__iexact=nazwa.strip()) |
            Q(skrot__iexact=nazwa.strip()))
    except Jednostka.DoesNotExist:
        pass


def matchuj_autora(imiona, nazwisko, jednostka, pesel_md5=None):
    if pesel_md5:
        try:
            return Autor.objects.get(pesel_md5__iexact=pesel_md5.strip())
        except Autor.DoesNotExist:
            pass

    try:

        qry = Q(
            Q(nazwisko__iexact=nazwisko.strip()) | Q(poprzednie_nazwiska__icontains=nazwisko.strip()),
            imiona__iexact=imiona.strip())

        return Autor.objects.get(qry)

    except Autor.MultipleObjectsReturned:

        try:
            return Autor.objects.get(qry & Q(aktualna_jednostka=jednostka))
        except Autor.MultipleObjectsReturned:
            pass
        except Autor.DoesNotExist:
            pass

    except Autor.DoesNotExist:
        pass


def przeanalizuj_plik_xls(sciezka, parent):
    """
    :param sciezka:
    :return: (success:boolean, message)
    """

    # Otwórz plik i sprawdź, czy w ogóle działa...
    try:
        f = xlrd.open_workbook(sciezka)
    except XLRDError as e:
        raise ImproperFileException(e)

    # Sprawdź, ile jest skoroszytów
    if len(f.sheets()) != 1:
        raise BadNoOfSheetsException()

    naglowek_row = None
    s = f.sheet_by_index(0)
    for n in range(s.nrows):
        r = [str(elem.value).lower() for elem in s.row(n)]
        if r == naglowek:
            naglowek_row = n
            break

    if naglowek_row is None:
        raise HeaderNotFoundException()

    for n in range(naglowek_row + 1, s.nrows):
        original = dict(zip(
            naglowek, [elem.value for elem in s.row(n)]
        ))

        if not original['nazwisko'].strip():
            continue

        original['pesel_md5'] = md5(str(original['pesel']).encode("utf-8")).hexdigest()
        del original['pesel']

        wydzial = matchuj_wydzial(original['wydział'])
        jednostka = matchuj_jednostke(original['nazwa jednostki'])
        autor = matchuj_autora(
            original['imię'],
            original['nazwisko'],
            jednostka,
            original['pesel_md5'])

        i = Import_Dyscyplin_Row.objects.create(
            row_no=n,
            parent=parent,
            original=original,
            jednostka=jednostka,
            wydzial=wydzial,
            autor=autor)

    return (True, "przeanalizowano %i rekordow" % (n - naglowek_row))

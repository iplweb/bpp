from hashlib import md5

import xlrd
from django.db.models import Q
from xlrd import XLRDError

from bpp.models import Wydzial, Jednostka, Autor
from import_dyscyplin.exceptions import BadNoOfSheetsException, HeaderNotFoundException, ImproperFileException
from import_dyscyplin.models import Import_Dyscyplin_Row

# naglowek = [
#     "lp", "tytuł/stopień", "nazwisko", "imię", "pesel",
#     "nazwa jednostki", "wydział",
#     "dyscyplina", "kod dyscypliny",
#     "subdyscyplina", "kod subdyscypliny"
# ]


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
            return (Autor.objects.get(pesel_md5__iexact=pesel_md5.strip()), "")
        except Autor.DoesNotExist:
            pass

    try:

        qry = Q(
            Q(nazwisko__iexact=nazwisko.strip()) | Q(poprzednie_nazwiska__icontains=nazwisko.strip()),
            imiona__iexact=imiona.strip())

        return (Autor.objects.get(qry), "")

    except Autor.MultipleObjectsReturned:

        try:
            return (Autor.objects.get(qry & Q(aktualna_jednostka=jednostka)), "")
        except Autor.MultipleObjectsReturned:
            return (
                None, "wielu autorów pasuje do tego rekordu (dopasowanie po imieniu, nazwisku i aktualnej jednostce)")

        except Autor.DoesNotExist:
            return (None, "taki autor nie istnieje (dopasowanie po imieniu, nazwisku i aktualnej jednostce)")

    except Autor.DoesNotExist:
        return (None, "taki autor nie istnieje (dopasowanie po imieniu i nazwisku)")


def pesel_md5(value_from_xls):
    """Zakoduj wartość PESEL z XLS, która to może być np liczbą
    zmiennoprzecinkową do sumy kontrolnej MD5.
    """
    original_pesel = value_from_xls

    if type(original_pesel) == int:
        original_pesel = str(original_pesel)
    elif type(original_pesel) == float:
        original_pesel = str(int(original_pesel))
    else:
        original_pesel = str(original_pesel)
    original_pesel = original_pesel.encode("utf-8")

    return md5(original_pesel).hexdigest()


def znajdz_naglowek(sciezka, try_names=['imię', 'imie', 'imiona', 'nazwisko', 'nazwiska', 'orcid', 'pesel'],
                    min_points=3):
    """
    :return: ([str, str...], no_row)
    """
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
        points = 0
        for elem in try_names:
            if elem in r:
                points += 1
        if points >= min_points:
            return r, n

    raise HeaderNotFoundException()


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

    if parent.kolumna_set.all().count() == 0:
        raise HeaderNotFoundException()

    naglowek = [k.rodzaj_pola for k in parent.kolumna_set.all()]

    wydzial_cache = {}
    jednostka_cache = {}

    for n in range(parent.wiersz_naglowka + 1, s.nrows):
        original = dict(zip(
            naglowek, [elem.value for elem in s.row(n)]
        ))

        if not original['nazwisko'].strip():
            continue

        original['pesel_md5'] = pesel_md5(original['pesel'])

        original['nazwa_jednostki'] = original['nazwa jednostki']  # templatka wymaga

        del original['pesel']

        wydzial = wydzial_cache.get(original['wydział'])
        if not wydzial:
            wydzial = wydzial_cache[original['wydział']] = matchuj_wydzial(original['wydział'])

        jednostka = jednostka_cache.get(original['nazwa jednostki'])
        if not jednostka:
            jednostka = jednostka_cache[original['nazwa jednostki']] = matchuj_jednostke(original['nazwa jednostki'])

        autor, info = matchuj_autora(
            original['imię'],
            original['nazwisko'],
            jednostka,
            original['pesel_md5'])

        Import_Dyscyplin_Row.objects.create(
            row_no=n,
            parent=parent,
            original=original,
            nazwisko=original['nazwisko'],
            imiona=original['imię'],
            nazwa_jednostki=original['nazwa_jednostki'],
            jednostka=jednostka,
            nazwa_wydzialu=original['wydział'],
            wydzial=wydzial,
            autor=autor,
            info=info,
            dyscyplina=original['dyscyplina'],
            kod_dyscypliny=original['kod dyscypliny'],
            subdyscyplina=original['subdyscyplina'],
            kod_subdyscypliny=original['kod subdyscypliny']
        )

    return (True, "przeanalizowano %i rekordow" % (n - parent.wiersz_naglowka))

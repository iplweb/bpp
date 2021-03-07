import xlrd
from _decimal import Decimal, InvalidOperation
from xlrd import XLRDError

from bpp.models import Jednostka
from import_common.core import matchuj_autora, matchuj_jednostke, matchuj_wydzial
from import_common.exceptions import (
    BadNoOfSheetsException,
    HeaderNotFoundException,
    ImproperFileException,
)
from import_dyscyplin.models import Import_Dyscyplin_Row


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

    s = f.sheet_by_index(0)

    if parent.kolumna_set.all().count() == 0:
        raise HeaderNotFoundException()

    naglowek = [k.rodzaj_pola for k in parent.kolumna_set.all()]

    wydzial_cache = {}
    jednostka_cache = {}

    for n in range(parent.wiersz_naglowka + 1, s.nrows):
        original = dict(zip(naglowek, [elem.value for elem in s.row(n)]))

        if not original["nazwisko"].strip():
            continue

        try:
            # templatka wymaga
            original["nazwa_jednostki"] = original["nazwa jednostki"]
        except KeyError:
            original["nazwa_jednostki"] = None

        try:
            wydzial = wydzial_cache.get(original["wydział"])
        except KeyError:
            wydzial = None

        if not wydzial:
            try:
                wydzial = wydzial_cache[original["wydział"]] = matchuj_wydzial(
                    original["wydział"]
                )
            except KeyError:
                pass

        try:
            jednostka = jednostka_cache.get(original["nazwa jednostki"])
        except KeyError:
            jednostka = None

        if not jednostka:
            try:
                jednostka = jednostka_cache[
                    original["nazwa jednostki"]
                ] = matchuj_jednostke(original["nazwa jednostki"])
            except (
                KeyError,
                Jednostka.DoesNotExist,
                Jednostka.MultipleObjectsReturned,
            ):
                jednostka = None

        autor = matchuj_autora(
            original["imię"],
            original["nazwisko"],
            jednostka=jednostka,
            orcid=original.get("orcid", None),
            pbn_id=original.get("pbn_id", None),
            tytul_str=original.get("tytuł"),
        )

        if autor is None:
            pass

        bledny = False

        for elem in ["procent dyscypliny", "procent subdyscypliny"]:
            v = original.get(elem)

            if v is None:
                continue

            if str(v) == "":
                original[elem] = None
                continue

            try:
                original[elem] = Decimal(original.get(elem))
            except (TypeError, InvalidOperation):
                original[elem] = None
                bledny = True

        if original.get("dyscyplina").strip() == "":
            bledny = True

        # import pdb; pdb.set_trace()
        i = Import_Dyscyplin_Row.objects.create(
            row_no=n,
            parent=parent,
            original=original,
            nazwisko=original["nazwisko"],
            imiona=original["imię"],
            nazwa_jednostki=original.get("nazwa_jednostki"),
            jednostka=jednostka,
            nazwa_wydzialu=original.get("wydział"),
            wydzial=wydzial,
            autor=autor,
            dyscyplina=original.get("dyscyplina"),
            kod_dyscypliny=original.get("kod dyscypliny"),
            procent_dyscypliny=original.get("procent dyscypliny"),
            subdyscyplina=original.get("subdyscyplina"),
            kod_subdyscypliny=original.get("kod subdyscypliny"),
            procent_subdyscypliny=original.get("procent subdyscypliny"),
        )

        if bledny:
            i.stan = Import_Dyscyplin_Row.STAN.BLEDNY
            i.info = "niepoprawna wartość w polu procent dyscypliny lub subdyscyliny"
            i.save()

    return (True, "przeanalizowano %i rekordow" % (n - parent.wiersz_naglowka))

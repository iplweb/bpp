import openpyxl
from _decimal import Decimal, InvalidOperation
from openpyxl.utils.exceptions import InvalidFileException

from import_common.core import matchuj_autora, matchuj_jednostke, matchuj_wydzial
from import_common.exceptions import (
    BadNoOfSheetsException,
    HeaderNotFoundException,
    ImproperFileException,
)
from import_dyscyplin.models import Import_Dyscyplin_Row

from bpp.models import Jednostka


def przeanalizuj_plik_xls(sciezka, parent):
    """
    :param sciezka:
    :return: (success:boolean, message)
    """

    # Otwórz plik i sprawdź, czy w ogóle działa...
    try:
        f = openpyxl.load_workbook(sciezka)
    except InvalidFileException as e:
        raise ImproperFileException(e)

    # Sprawdź, ile jest skoroszytów
    if len(f.worksheets) != 1:
        raise BadNoOfSheetsException()

    s = f.worksheets[0]

    if parent.kolumna_set.all().count() == 0:
        raise HeaderNotFoundException()

    naglowek = [k.rodzaj_pola for k in parent.kolumna_set.all()]

    wydzial_cache = {}
    jednostka_cache = {}

    for n, row in enumerate(
        s.iter_rows(
            min_row=parent.wiersz_naglowka + 1, max_row=s.max_row, values_only=True
        ),
        parent.wiersz_naglowka + 1,
    ):
        original = dict(zip(naglowek, [elem for elem in row]))

        if original["nazwisko"] is None or (not original["nazwisko"].strip()):
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

        # Akceptujemy pliki bez pierwszej dyscypliny -- taki zapis w pliku oznacza,
        # że autorowi dyscyplina jest kasowana. Zatem, poniższy kod zostaje usunięty:
        # if original.get("dyscyplina").strip() == "":
        #     bledny = True

        i = Import_Dyscyplin_Row(
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

        if i.dyscyplina is None:
            i.procent_dyscypliny = None

        if i.subdyscyplina is None:
            i.procent_subdyscypliny = None

        if autor is None:
            i.stan = Import_Dyscyplin_Row.STAN.BLEDNY
            i.info = "Nie można dopasować autora"
        else:
            if i.dyscyplina is None and i.subdyscyplina is not None:
                i.stan = Import_Dyscyplin_Row.STAN.BLEDNY
                i.info = "Dyscyplina pusta, subdyscyplina ustawiona."

            elif bledny:
                i.stan = Import_Dyscyplin_Row.STAN.BLEDNY
                i.info = (
                    "niepoprawna wartość w polu procent dyscypliny lub subdyscypliny"
                )

        i.save()

    return (True, "przeanalizowano %i rekordow" % (n - parent.wiersz_naglowka))

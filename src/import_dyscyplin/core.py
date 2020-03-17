from _decimal import Decimal, InvalidOperation
from hashlib import md5

import xlrd
from django.core.exceptions import MultipleObjectsReturned
from django.db.models import Q
from xlrd import XLRDError

from bpp.models import Autor, Autor_Jednostka, Jednostka, Wydzial
from import_dyscyplin.exceptions import (
    BadNoOfSheetsException,
    HeaderNotFoundException,
    ImproperFileException,
)
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
            Q(nazwa__iexact=nazwa.strip()) | Q(skrot__iexact=nazwa.strip())
        )
    except MultipleObjectsReturned:
        return None
    except Jednostka.DoesNotExist:
        pass


def matchuj_autora(
    imiona,
    nazwisko,
    jednostka=None,
    pesel_md5=None,
    pbn_id=None,
    orcid=None,
    tytul_str=None,
):
    if pbn_id is not None:
        if type(pbn_id) == str:
            pbn_id = pbn_id.strip()

        try:
            pbn_id = int(pbn_id)
        except (TypeError, ValueError):
            pbn_id = None

        if pbn_id is not None:
            try:
                return (Autor.objects.get(pbn_id=pbn_id), "")
            except Autor.DoesNotExist:
                pass

    if pesel_md5:
        try:
            return (Autor.objects.get(pesel_md5__iexact=pesel_md5.strip()), "")
        except Autor.DoesNotExist:
            pass

    if orcid:
        try:

            return (Autor.objects.get(orcid__iexact=orcid.strip()), "")
        except Autor.DoesNotExist:
            pass

    queries = [
        Q(
            Q(nazwisko__iexact=nazwisko.strip())
            | Q(poprzednie_nazwiska__icontains=nazwisko.strip()),
            imiona__iexact=imiona.strip(),
        )
    ]
    if tytul_str:
        queries.append(queries[0] & Q(tytul__skrot=tytul_str))

    for qry in queries:
        try:
            return (Autor.objects.get(qry), "")
        except (Autor.DoesNotExist, Autor.MultipleObjectsReturned):
            pass

        # wdrozyc matchowanie po tytule
        # wdrozyc matchowanie po jednostce
        # testy mają przejść
        # commit do głównego brancha
        # mbockowska odpisać na zgłoszenie w mantis

        try:
            return (Autor.objects.get(qry & Q(aktualna_jednostka=jednostka)), "")
        except (Autor.MultipleObjectsReturned, Autor.DoesNotExist):
            pass

    # Jesteśmy tutaj. Najwyraźniej poszukiwanie po aktualnej jednostce, imieniu, nazwisku,
    # tytule itp nie bardzo się powiodło. Spróbujmy innej strategii -- jednostka jest
    # określona, poszukajmy w jej autorach. Wszak nie musi być ta jednostka jednostką
    # aktualną...

    if jednostka:

        queries = [
            Q(
                Q(autor__nazwisko__iexact=nazwisko.strip())
                | Q(autor__poprzednie_nazwiska__icontains=nazwisko.strip()),
                autor__imiona__iexact=imiona.strip(),
            )
        ]
        if tytul_str:
            queries.append(queries[0] & Q(autor__tytul__skrot=tytul_str))

        for qry in queries:
            try:
                return (jednostka.autor_jednostka_set.get(qry).autor, "")
            except (
                Autor_Jednostka.MultipleObjectsReturned,
                Autor_Jednostka.DoesNotExist,
            ):
                pass

    return (None, "nie udało się dopasować")


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


def znajdz_naglowek(
    sciezka,
    try_names=[
        "imię",
        "imie",
        "imiona",
        "nazwisko",
        "nazwiska",
        "orcid",
        "pesel",
        "pbn-id",
        "pbn_id",
        "pbn id",
    ],
    min_points=3,
):
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
            original["pesel_md5"] = pesel_md5(original["pesel"])
            del original["pesel"]
        except KeyError:
            original["pesel_md5"] = None

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
            except KeyError:
                jednostka = None

        autor, info = matchuj_autora(
            original["imię"],
            original["nazwisko"],
            jednostka=jednostka,
            pesel_md5=original.get("pesel_md5", None),
            orcid=original.get("orcid", None),
            pbn_id=original.get("pbn_id", None),
            tytul_str=original["tytuł"],
        )

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
            info=info,
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

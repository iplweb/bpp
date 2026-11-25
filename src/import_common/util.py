from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from django.utils.functional import cached_property
from django.views.decorators.debug import sensitive_variables

from .exceptions import (
    BadNoOfSheetsException,
    DecompressionBombException,
    HeaderNotFoundException,
    ImproperFileException,
    NieprawidloweHasloDoPlikuException,
    PlikZabezpieczonyHaslemException,
    PlikZaDuzyException,
)

# Limit rozmiaru pliku XLSX PO dekompresji. Realne pliki importowe (nawet
# kilkanaście MB XLSX) rozpakowują się do najwyżej dziesiątek/setek MB XML —
# 500 MB daje spory zapas, a bomba zip (KB → GB) go przekracza i jest
# odrzucana przed załadowaniem do pamięci (obrona przed OOM workera importu).
MAX_ROZMIAR_PO_DEKOMPRESJI = 500 * 1024 * 1024

# Limit rozmiaru samego pliku NA DYSKU. Bomb-check pilnuje rozmiaru po
# dekompresji, ale „gruby" formalnie-legalny XLSX (~setki MB), który po
# dekompresji mieści się pod progiem, i tak wciągnąłby cały skoroszyt do RAM.
# 100 MB z zapasem pokrywa realne importy, a odcina wektor OOM przed load.
MAX_ROZMIAR_PLIKU = 100 * 1024 * 1024


def _rozmiar(plik):
    """Rozmiar pliku na dysku: ścieżka (str/Path) albo obiekt plikowy Django
    (``UploadedFile``/``FieldFile`` z atrybutem ``size``). ``None`` = nie da
    się ustalić (brak pliku) — nie ten wektor, niech padnie dalej."""
    import os

    if isinstance(plik, (str, os.PathLike)):
        try:
            return os.path.getsize(plik)
        except OSError:
            return None
    try:
        return plik.size
    except (AttributeError, OSError, ValueError):
        return None


def sprawdz_rozmiar_pliku(sciezka, max_bajtow=None):
    """Odrzuca plik większy niż ``max_bajtow`` PRZED załadowaniem do pamięci.

    ``sciezka`` może być ścieżką albo obiektem plikowym Django (``.size``).
    Domyślny limit (``MAX_ROZMIAR_PLIKU``) jest czytany w chwili wywołania."""
    if max_bajtow is None:
        max_bajtow = MAX_ROZMIAR_PLIKU
    rozmiar = _rozmiar(sciezka)
    if rozmiar is None:
        return
    if rozmiar > max_bajtow:
        raise PlikZaDuzyException(
            f"Rozmiar pliku ({rozmiar} B) przekracza bezpieczny limit "
            f"({max_bajtow} B) — plik odrzucony przed przetwarzaniem."
        )


def sprawdz_bombe_dekompresji(sciezka, max_rozpakowany=None):
    """Odrzuca XLSX-owe (ZIP) bomby dekompresyjne PRZED załadowaniem do pamięci.

    XLSX to archiwum ZIP; złośliwy plik ~KB może rozpakować się do GB i zabić
    workera importu (OOM). Sumujemy deklarowane rozmiary po dekompresji z
    centralnego katalogu ZIP (bez faktycznego rozpakowywania) i odrzucamy plik
    przekraczający ``max_rozpakowany``. Pliki nie-ZIP (stary .xls OLE, .csv)
    nie są bombami tego typu → cicho przepuszczamy (inny wektor).

    ``sciezka`` może być ścieżką albo obiektem plikowym (pozycja odczytu jest
    przywracana, bo zaraz po nas ten sam obiekt czyta openpyxl). Domyślny
    limit (``MAX_ROZMIAR_PO_DEKOMPRESJI``) jest czytany w chwili wywołania.
    """
    import zipfile

    if max_rozpakowany is None:
        max_rozpakowany = MAX_ROZMIAR_PO_DEKOMPRESJI

    pozycja = None
    if hasattr(sciezka, "seek") and hasattr(sciezka, "tell"):
        pozycja = sciezka.tell()
    try:
        with zipfile.ZipFile(sciezka) as zf:
            rozpakowany = sum(info.file_size for info in zf.infolist())
    except zipfile.BadZipFile:
        return  # nie-ZIP (np. .xls / .csv) — nie ten wektor
    finally:
        if pozycja is not None:
            sciezka.seek(pozycja)

    if rozpakowany > max_rozpakowany:
        raise DecompressionBombException(
            f"Rozmiar pliku po dekompresji ({rozpakowany} B) przekracza "
            f"bezpieczny limit ({max_rozpakowany} B) — plik odrzucony jako "
            f"potencjalna bomba dekompresyjna."
        )


# Sygnatura kontenera OLE2 (Compound File Binary). Ma ją stary .xls ORAZ
# każdy plik Office zaszyfrowany hasłem — także .xlsx, który po zaszyfrowaniu
# przestaje być archiwum ZIP i staje się OLE2 ze strumieniami
# ``EncryptionInfo`` + ``EncryptedPackage``.
SYGNATURA_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

# Jak zdjąć hasło w Excelu — wspólny fragment komunikatów dla użytkownika.
INSTRUKCJA_USUNIECIA_HASLA = (
    "otwórz plik w Excelu, usuń hasło (Plik → Informacje → Chroń skoroszyt → "
    "Zaszyfruj przy użyciu hasła → wyczyść pole), zapisz plik i wgraj go ponownie."
)

KOMUNIKAT_PLIK_Z_HASLEM = (
    "Plik jest zabezpieczony hasłem i nie da się go odczytać. Aby go "
    "zaimportować, " + INSTRUKCJA_USUNIECIA_HASLA
)

KOMUNIKAT_NIEPRAWIDLOWE_HASLO = "Nieprawidłowe hasło do pliku."

KOMUNIKAT_NIE_DA_SIE_ODSZYFROWAC = (
    "Nie udało się odszyfrować pliku — plik jest uszkodzony albo ten rodzaj "
    "zabezpieczenia nie jest obsługiwany. Zamiast podawać hasło, "
    + INSTRUKCJA_USUNIECIA_HASLA
)

# Limit rozmiaru pliku zabezpieczonego hasłem, który odszyfrowujemy w procesie
# HTTP. msoffcrypto trzyma całość w pamięci, a dla .xls (BIFF) buduje listę
# Pythona z pozycją na KAŻDY bajt (~8 B wskaźnika na bajt pliku) — 100 MB
# zwykłego limitu to ryzyko OOM. Eksporty z POL-on mają pojedyncze MB.
MAX_ROZMIAR_PLIKU_Z_HASLEM = 10 * 1024 * 1024


@contextmanager
def _strumien_binarny(plik):
    """Otwiera ``plik`` (ścieżka albo obiekt plikowy Django) do odczytu
    binarnego. Dla obiektu plikowego przywraca pozycję odczytu po wyjściu —
    zaraz po nas ten sam obiekt czyta parser. ``None`` = pliku nie da się
    otworzyć (brak pliku): to nie ten wektor, niech padnie dalej."""
    import os

    if isinstance(plik, (str, os.PathLike)):
        try:
            f = open(plik, "rb")  # zamykany w finally niżej
        except OSError:
            yield None  # brak/nieczytelny plik — błąd zgłosi parser
            return
        try:
            yield f
        finally:
            f.close()
        return

    if not all(hasattr(plik, a) for a in ("read", "seek", "tell")):
        yield None  # nie plik — nie ten wektor
        return

    pozycja = plik.tell()
    try:
        plik.seek(0)
        yield plik
    finally:
        plik.seek(pozycja)


class HasloDoPliku:
    """Hasło do zaszyfrowanego pliku, które nie pokazuje się w ``repr``/``str``.

    Monitoring błędów (Sentry/GlitchTip, Rollbar) i raport błędu Django
    zapisują zmienne lokalne i argumenty KAŻDEJ ramki tracebacku — także
    krotki ``*args`` dekoratorów (np. ``sensitive_variables``), gdzie nie ma
    nazwy klucza, po której dałoby się wartość zamazać. Przekazujemy więc
    wszędzie ten obiekt, a jawną wartość wyjmujemy (``odslon()``) dopiero
    w wywołaniu biblioteki odszyfrowującej, bez przypisywania do zmiennej.
    """

    __slots__ = ("_wartosc",)
    ZAMASKOWANE = "********"

    def __init__(self, wartosc=""):
        self._wartosc = wartosc or ""

    def __bool__(self):
        return bool(self._wartosc)

    def __repr__(self):
        return f"HasloDoPliku({self.ZAMASKOWANE!r})"

    def __str__(self):
        return self.ZAMASKOWANE

    def odslon(self):
        return self._wartosc


def _odslon(haslo):
    if isinstance(haslo, HasloDoPliku):
        return haslo.odslon()
    return haslo


# Rekordy BIFF (.xls): BOF globals, FILEPASS (= plik zaszyfrowany), EOF.
_BIFF_FILEPASS = 0x002F
_BIFF_EOF = 0x000A


def _xls_ma_filepass(f, ole):
    """Czy strumień ``Workbook`` (.xls, BIFF8) zaczyna się od rekordu FILEPASS?

    FILEPASS stoi zaraz po BOF podstrumienia globals, więc wystarczy PIERWSZY
    sektor strumienia — czytamy go wprost z pliku, bez ``openstream()``
    (olefile i ``msoffcrypto.Xls97File`` wczytują cały strumień do pamięci,
    a to dzieje się PRZED sprawdzeniem limitów rozmiaru pliku z hasłem)."""
    import struct

    wpis = next((k for k in ole.root.kids if k.name.lower() == "workbook"), None)
    if wpis is None:
        return False
    if wpis.size < ole.minisectorcutoff:
        # Mały strumień (< 4 KB) siedzi w ministrumieniu — tani odczyt.
        dane = ole.openstream(wpis.name).read(ole.sectorsize)
    else:
        f.seek((wpis.isectStart + 1) * ole.sectorsize)
        dane = f.read(min(ole.sectorsize, wpis.size))

    poz = 0
    while poz + 4 <= len(dane):
        numer, rozmiar = struct.unpack_from("<HH", dane, poz)
        if numer == _BIFF_FILEPASS:
            return True
        if numer == _BIFF_EOF:
            return False
        poz += 4 + rozmiar
    return False


def czy_plik_zaszyfrowany(plik):
    """Czy ``plik`` (ścieżka albo obiekt plikowy) to dokument Office
    zaszyfrowany hasłem (XLSX/XLS „Zaszyfruj przy użyciu hasła")?

    Czyta tylko nagłówek i katalog OLE2 (plus pierwszy sektor strumienia
    ``Workbook`` dla .xls) — nie parsuje metadanych szyfrowania i nie
    odszyfrowuje niczego. Pliki nie-OLE2 (zwykły XLSX/ZIP, CSV) od razu dają
    ``False``. Kontener z TYLKO jednym ze strumieni szyfrowania (uszkodzony
    plik z hasłem) daje ``PlikZabezpieczonyHaslemException`` „uszkodzony"."""
    with _strumien_binarny(plik) as f:
        if f is None or f.read(len(SYGNATURA_OLE2)) != SYGNATURA_OLE2:
            return False

        import struct

        import olefile

        try:
            f.seek(0)
            ole = olefile.OleFileIO(f)
            info = ole.exists("EncryptionInfo")
            pakiet = ole.exists("EncryptedPackage")
            if info or pakiet:
                if not (info and pakiet):
                    raise PlikZabezpieczonyHaslemException(
                        KOMUNIKAT_NIE_DA_SIE_ODSZYFROWAC
                    )
                # Zaszyfrowany OOXML (.xlsx) — po samych strumieniach.
                return True
            return _xls_ma_filepass(f, ole)
        except (OSError, ValueError, IndexError, KeyError, struct.error):
            # OLE2, ale uszkodzony kontener (olefile rzuca ``OSError``/
            # ``ValueError``). To nie jest „plik z hasłem" — błąd formatu
            # zgłosi parser niżej.
            return False


def sprawdz_szyfrowanie_pliku(plik):
    """Odrzuca plik zaszyfrowany hasłem PRZED parsowaniem, z komunikatem dla
    użytkownika (zamiast „Can't find workbook in OLE2 compound document")."""
    if czy_plik_zaszyfrowany(plik):
        raise PlikZabezpieczonyHaslemException(KOMUNIKAT_PLIK_Z_HASLEM)


@sensitive_variables("haslo")
def odszyfruj_plik(plik, haslo):
    """Odszyfrowuje dokument Office zabezpieczony hasłem; zwraca bajty pliku
    już BEZ hasła (XLSX → zwykły ZIP, XLS → zwykły BIFF).

    ``plik`` — ścieżka albo obiekt plikowy. Rzuca
    ``NieprawidloweHasloDoPlikuException`` przy złym haśle i
    ``PlikZabezpieczonyHaslemException`` przy zabezpieczeniu, którego nie
    umiemy zdjąć. Hasło NIE trafia do żadnego komunikatu ani łańcucha
    wyjątków (``from None``) — nie wolno go też logować w miejscu wywołania.

    Plik większy niż ``MAX_ROZMIAR_PLIKU_Z_HASLEM`` jest odrzucany PRZED
    odszyfrowaniem (``PlikZaDuzyException``). Wynik trzeba przepuścić przez
    ``sprawdz_plik_importu`` jak każdy inny plik — odszyfrowany XLSX też może
    być bombą dekompresyjną."""
    import io
    import logging
    import struct
    from xml.parsers.expat import ExpatError

    import msoffcrypto
    from msoffcrypto.exceptions import (
        DecryptionError,
        FileFormatError,
        InvalidKeyError,
        ParseError,
    )

    rozmiar = _rozmiar(plik)
    if rozmiar is not None and rozmiar > MAX_ROZMIAR_PLIKU_Z_HASLEM:
        raise PlikZaDuzyException(
            f"Plik zabezpieczony hasłem jest za duży, żeby odszyfrować go na "
            f"serwerze ({rozmiar / 1024 / 1024:.1f} MB, limit "
            f"{MAX_ROZMIAR_PLIKU_Z_HASLEM // 1024 // 1024} MB). Zamiast podawać "
            f"hasło, " + INSTRUKCJA_USUNIECIA_HASLA
        )

    wynik = io.BytesIO()
    with _strumien_binarny(plik) as f:
        if f is None:
            raise PlikZabezpieczonyHaslemException(KOMUNIKAT_NIE_DA_SIE_ODSZYFROWAC)
        try:
            dokument = msoffcrypto.OfficeFile(f)
            # Jawne hasło tylko w argumencie wywołania — bez zmiennej lokalnej.
            dokument.load_key(password=_odslon(haslo))
            dokument.decrypt(wynik)
        except InvalidKeyError:
            raise NieprawidloweHasloDoPlikuException(
                KOMUNIKAT_NIEPRAWIDLOWE_HASLO
            ) from None
        except (
            DecryptionError,
            FileFormatError,
            ParseError,
            OSError,
            ValueError,
            IndexError,
            KeyError,
            ExpatError,
            AssertionError,
            struct.error,
        ) as e:
            # Nieobsługiwany wariant szyfrowania albo uszkodzony plik (msoffcrypto
            # przy złych metadanych rzuca m.in. ``IndexError``/``KeyError``,
            # ``ExpatError`` z XML-a EncryptionInfo) — błąd użytkownika (ma
            # zdjąć hasło w Excelu), nie aplikacji. Logujemy tylko typ wyjątku.
            logging.getLogger(__name__).info(
                "Nie udało się odszyfrować pliku importu: %s", type(e).__name__
            )
            raise PlikZabezpieczonyHaslemException(
                KOMUNIKAT_NIE_DA_SIE_ODSZYFROWAC
            ) from None
    return wynik.getvalue()


def sprawdz_plik_importu(sciezka, max_bajtow=None, max_rozpakowany=None):
    """Wspólny bezpiecznik dla plików importu wgrywanych przez użytkownika:
    limit rozmiaru na dysku + (dla XLSX/ZIP) limit rozmiaru po dekompresji +
    odrzucenie pliku zaszyfrowanego hasłem. Wołać PRZED parsowaniem
    (openpyxl/pandas/csv). Rzuca podklasę ``NiebezpiecznyPlikException``
    z czytelnym komunikatem."""
    sprawdz_rozmiar_pliku(sciezka, max_bajtow=max_bajtow)
    sprawdz_bombe_dekompresji(sciezka, max_rozpakowany=max_rozpakowany)
    sprawdz_szyfrowanie_pliku(sciezka)


# openpyxl importujemy LOKALNIE (nie na poziomie modułu): ten moduł jest
# importowany eager przez modele importerów (np. import_list_if.models →
# XLSImportFile) już przy django.setup(), a openpyxl przez compat/numbers.py
# ciągnie całe numpy
# (~tens MB RSS) do KAŻDEGO procesu — także web/ASGI, który nigdy nie czyta
# xlsx. Dzięki PEP 563 (future annotations) adnotacje typu ``openpyxl.*``
# w sygnaturach poniżej są tylko łańcuchami i nie wymagają openpyxl w
# runtime; pod TYPE_CHECKING dajemy je type-checkerom/ruff. Plik xlsx
# otwierają tylko funkcje z lokalnym importem.
if TYPE_CHECKING:
    import openpyxl

DEFAULT_COL_NAMES = [
    "imię",
    "imie",
    "imiona",
    "nazwisko",
    "nazwiska",
    "orcid",
    "pesel",
    "pbn_id",
    "stanowisko",
    "wydział",
    "jednostka",
    "numer",
]

DEFAULT_MIN_POINTS = 3


def normalize_cell_header(value):
    """Normalizuje SUROWĄ wartość komórki nagłówka (str/None/liczba/datetime),
    NIE openpyxl ``Cell`` — dzięki temu ten sam kod obsługuje XLSX (openpyxl)
    i CSV (stringi)."""
    s = str(value).lower().split("\n")[0]

    s = s.replace(".", " ")
    while s.find("  ") >= 0:
        s = s.replace("  ", " ")
    s = s.strip()

    return s.replace(" ", "_").replace("/", "_").replace("\\", "_").replace("-", "_")


def find_similar_row_in_rows(rows, try_names=None, min_points=None, max_row_length=128):
    """Rdzeń fuzzy-detekcji nagłówka nad gołymi listami wartości.

    :param rows: iterowalne wierszy; każdy wiersz to lista wartości (str/None/…)
    :return: ``(znormalizowane_nazwy, n_1based)`` pierwszego wiersza z
        ``>= min_points`` trafień, albo ``None``.
    """
    if try_names is None:
        try_names = DEFAULT_COL_NAMES

    if min_points is None:
        min_points = DEFAULT_MIN_POINTS

    for n, row in enumerate(rows, start=1):
        r = [normalize_cell_header(v) for v in row[:max_row_length]]
        points = 0
        for elem in try_names:
            if elem in r:
                points += 1
        if points >= min_points:
            return r, n


def find_similar_row(sheet, try_names=None, min_points=None, max_row_length=128):
    """Wrapper zachowujący dotychczasową sygnaturę (arkusz openpyxl):
    wyciąga ``cell.value`` z każdej komórki i deleguje do
    ``find_similar_row_in_rows``. Istniejący callerzy (``znajdz_naglowek``,
    ``XLSImportFile``) nie wymagają zmian."""
    rows = ([cell.value for cell in row] for row in sheet.rows)
    return find_similar_row_in_rows(rows, try_names, min_points, max_row_length)


def znajdz_naglowek(
    sciezka,
    try_names=None,
    min_points=None,
):
    """
    :return: ([str, str...], no_row)
    """
    import openpyxl
    from openpyxl.utils.exceptions import InvalidFileException

    sprawdz_rozmiar_pliku(sciezka)
    sprawdz_bombe_dekompresji(sciezka)
    sprawdz_szyfrowanie_pliku(sciezka)
    try:
        # read_only: czytamy strumieniowo (tylko cell.value + iteracja rows),
        # bez wciągania całego skoroszytu do RAM — obrona przed OOM workera.
        f: openpyxl.workbook.workbook.Workbook = openpyxl.load_workbook(
            sciezka, read_only=True
        )
    except InvalidFileException as e:
        raise ImproperFileException(e) from e

    # Sprawdź, ile jest skoroszytów
    if len(f.worksheets) != 1:
        raise BadNoOfSheetsException()

    s = f.worksheets[0]

    res = find_similar_row(s, try_names, min_points)

    if res is None:
        raise HeaderNotFoundException()

    return res


DEFAULT_BANNED_NAMES = ["pesel", "pesel_md5", "peselmd5"]


class XLSImportFile:
    def __init__(
        self,
        xls_path,
        try_names=None,
        min_points=None,
        banned_names=None,
        only_first_sheet=False,
    ):
        """
        :param xls_path: ścieżka do pliku
        :param try_names: nazwy które będą poszukiwane jako nagłówek
        :param min_points: ile z nazw nagłówka musi się odnaleźć w wierszu, żeby był tak potraktowany
        :param banned_names: niedozwolone nazwy nagłówków - te kolumny nie będą importowane (np PESEL)
        """

        self.xls_path = xls_path
        self.try_names = try_names
        self.min_points = min_points

        if banned_names is None:
            banned_names = DEFAULT_BANNED_NAMES
        self.banned_names = banned_names

        self.only_first_sheet = only_first_sheet

    @cached_property
    def xl_workbook(self) -> openpyxl.workbook.workbook.Workbook:
        import openpyxl

        sprawdz_rozmiar_pliku(self.xls_path)
        sprawdz_bombe_dekompresji(self.xls_path)
        sprawdz_szyfrowanie_pliku(self.xls_path)
        # read_only: strumieniowy odczyt (iteracja rows + cell.value) bez
        # ładowania całego skoroszytu do RAM — obrona przed OOM workera.
        return openpyxl.load_workbook(self.xls_path, read_only=True)

    @cached_property
    def sheet_limit_range_end(self):
        limit = None
        if self.only_first_sheet:
            limit = 1
        return limit

    @cached_property
    def sheet_row_cache(self):
        _cache = {}

        for _n_sheet, sheet in enumerate(
            self.xl_workbook.worksheets[: self.sheet_limit_range_end]
        ):
            res = find_similar_row(
                sheet, try_names=self.try_names, min_points=self.min_points
            )
            if res is None:
                continue
            _cache[sheet] = res
        return _cache

    @staticmethod
    def _pusty(values) -> bool:
        """Wiersz pusty = wszystkie komórki danych ``None`` albo białe znaki.
        openpyxl ``sheet.max_row`` obejmuje puste wiersze końcowe (Excel śledzi
        „użyty zakres" — stąd rozjazd `max_row` z realną liczbą danych), więc
        bez tego filtra puste wiersze trafiają do pipeline'u i wywalają
        walidację wymaganych pól (nazwisko/imię) — cały import pada na jednym
        pustym wierszu na końcu arkusza. Zwierciadło ``CSVSource._pusty``."""
        return not any((str(v).strip() if v is not None else "") for v in values)

    def count(self) -> int:
        """
        Zwraca całkowitą liczbę NIEPUSTYCH wierszy do analizy — spójne z
        ``data()`` (puste wiersze pomijamy po obu stronach, inaczej pasek
        postępu nigdy nie dobija do 100%).
        """
        total = 0
        for sheet in self.xl_workbook.worksheets:
            res = self.sheet_row_cache.get(sheet)
            if res is None:
                continue
            labels, no = res
            for n_row, row in enumerate(sheet.rows):
                if n_row < no:
                    continue
                if self._pusty(cell.value for cell in row[: len(labels)]):
                    continue
                total += 1

        return total

    def liczba_arkuszy_z_danymi(self) -> int:
        """Liczba arkuszy z rozpoznanym nagłówkiem (= arkuszy z danymi).
        Importy wymuszające „jeden arkusz = jeden import" (np. import
        pracowników) używają tego do odrzucenia plików wieloarkuszowych: dwa
        arkusze w jednym skoroszycie to zwykle dwa rozłączne zbiory (np. dwie
        uczelnie), których nie wolno po cichu skleić w jeden import."""
        return len(self.sheet_row_cache)

    def data(self) -> Generator[dict, None, None]:
        """
        Ta funkcja dla każdego arkusza:
        1) znajduje nagłówek za pomoca funkcji `find_similar_row`,
        2) wczytuje poniższe wiersze do końca arkusza,
        3) dla każdego wiersza przypisuje nazwy kolumn z wiersza nagłówkowego
        4) zwraca słowniki.
        """

        for n_sheet, sheet in enumerate(self.xl_workbook.worksheets):
            res = self.sheet_row_cache.get(sheet)
            if res is None:
                continue

            colnames, no = res

            colnames = rename_duplicate_columns(colnames)

            colnames.append("__xls_loc_sheet__")
            colnames.append("__xls_loc_row__")

            for n_row, row in enumerate(sheet.rows):
                if n_row < res[1]:
                    continue
                data = [x.value for x in row[: len(colnames) - 2]]
                if self._pusty(data):
                    continue
                data.append(n_sheet)
                data.append(n_row)

                yld = dict(zip(colnames, data, strict=False))

                for banned_name in self.banned_names:
                    if banned_name in yld:
                        del yld[banned_name]

                yield yld


def rename_duplicate_columns(s: list[str], marker: str = "_") -> list[str]:
    seen = defaultdict(lambda: 1)
    ret = []
    for elem in s:
        no_seen = seen[elem]
        if no_seen == 1:
            ret.append(elem)
        else:
            ret.append(f"{elem}{marker}{no_seen}")
        seen[elem] += 1
    return ret


doi_regexp = re.compile(r"10.\d{4,9}/[-._;()/:A-Za-z0-9]+")


def strip_doi_urls(s: str) -> str:
    if not s:
        return

    return (
        s.replace("https://dx.doi.org/", "")
        .replace("http://dx.doi.org/", "")
        .replace("https://doi.org/", "")
        .replace("http://doi.org/", "")
        .replace("dx.doi.org/", "")
        .replace("doi.org/", "")
        .strip()
    )


def check_if_doi(s: str):
    """Sprawdza, czy wpisany ciąg znaków to może być DOI, POD WARUNKIEM że
    numeryczne DOI jest na początku (bez spacji itp)"""

    if not s:
        return False

    s = strip_doi_urls(s)

    ret = doi_regexp.search(s)
    if ret is not None:
        if ret.span()[0] == 0:
            return True

    return False

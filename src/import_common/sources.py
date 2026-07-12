"""Warstwa źródeł tabelarycznych dla importów (XLSX + CSV).

``TabularSource`` to wspólny protokół (``count()`` + ``data()``), którego
oczekuje pipeline importu. ``XLSXSource`` opakowuje istniejący
``XLSImportFile`` (openpyxl) bez zmian logiki parsowania. ``CSVSource``
(Task 3) dokłada obsługę CSV. ``otworz_zrodlo`` (Task 5) wykrywa format po
magic-bytes i zwraca właściwą implementację.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from typing import Protocol

from django.utils.functional import cached_property

from .exceptions import HeaderNotFoundException
from .util import (
    DEFAULT_BANNED_NAMES,
    XLSImportFile,
    find_similar_row_in_rows,
    rename_duplicate_columns,
)


class TabularSource(Protocol):
    """Minimalny kontrakt konsumowany przez pipeline importu.

    ``data()`` MUSI emitować w każdym słowniku klucze lokalizacyjne
    ``__xls_loc_sheet__`` i ``__xls_loc_row__`` (kontrakt sortowania
    ``get_details_set``)."""

    def count(self) -> int: ...

    def data(self) -> Iterator[dict]: ...

    def liczba_arkuszy_z_danymi(self) -> int:
        """Liczba arkuszy z danymi (CSV = zawsze 1). Importy „jeden arkusz =
        jeden import" odrzucają plik, gdy > 1."""
        ...


class XLSXSource:
    """Adapter na istniejący ``XLSImportFile`` (openpyxl)."""

    def __init__(self, path, *, try_names=None, min_points=None, banned_names=None):
        self._xif = XLSImportFile(
            path,
            try_names=try_names,
            min_points=min_points,
            banned_names=banned_names,
        )

    def count(self) -> int:
        return self._xif.count()

    def data(self) -> Iterator[dict]:
        return self._xif.data()

    def liczba_arkuszy_z_danymi(self) -> int:
        return self._xif.liczba_arkuszy_z_danymi()


def wykryj_format(path) -> str:
    """Wykrywa format po MAGIC-BYTES, nie po rozszerzeniu (ludzie nazywają
    ``.xls`` plik CSV i odwrotnie). XLSX = archiwum ZIP → zaczyna się od PEŁNEJ
    sygnatury local-file-header ``b"PK\\x03\\x04"`` (4 bajty, nie samo ``PK`` —
    inaczej CSV z pierwszą kolumną „PKD"/„PKB"/„PK" byłby wzięty za XLSX i
    wywalił openpyxl). Reszta = CSV (stary binarny ``.xls`` BIFF nie jest
    wspierany — openpyxl i tak go nie czyta)."""
    with open(path, "rb") as f:
        sygnatura = f.read(4)
    if sygnatura == b"PK\x03\x04":
        return "xlsx"
    return "csv"


def _zdekoduj(raw: bytes) -> str:
    """Dekoduje bajty CSV, próbując kolejno: ``utf-8-sig`` (BOM), ``cp1250``
    (Excel na Windows), ``iso-8859-2``. ``utf-8-sig`` jest realnym
    dyskryminatorem: rzuca ``UnicodeDecodeError`` na bajtach spoza UTF-8 (np.
    polskie znaki w cp1250), więc pliki UTF-8 łapią się pierwsze, a cp1250
    dopiero gdy UTF-8 zawiedzie. **Uwaga:** cp1250 dekoduje niemal każdy bajt
    (tylko 5 jest niezdefiniowanych), więc gałąź ``iso-8859-2`` jest w praktyce
    martwa — plik faktycznie w iso-8859-2 zwykle „poprawnie" (bez wyjątku)
    zdekoduje się jako cp1250 z przekłamanymi kilkoma znakami. Rozróżnienie
    cp1250/iso wymagałoby heurystyki częstości znaków — poza zakresem Fazy 1."""
    for enc in ("utf-8-sig", "cp1250", "iso-8859-2"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    # Ostateczność — nie powinno się zdarzyć (cp1250 dekoduje ~wszystko):
    return raw.decode("utf-8", errors="replace")


def _wykryj_delimiter(tekst: str) -> str:
    """Wykrywa delimiter CSV. ``csv.Sniffer`` na pierwszych ~5 liniach, z
    fallbackiem „policz ``;`` vs ``,`` vs tab" (Sniffer bywa kruchy na
    jednokolumnowych plikach). Domyślnie ``;`` — polski Excel."""
    probka = "\n".join(tekst.splitlines()[:5])
    try:
        return csv.Sniffer().sniff(probka, delimiters=";,\t").delimiter
    except csv.Error:
        # Sniffer nie rozpoznał — policz ręcznie:
        liczby = {d: probka.count(d) for d in (";", ",", "\t")}
        najlepszy = max(liczby, key=liczby.get)
        return najlepszy if liczby[najlepszy] > 0 else ";"


class CSVSource:
    """Źródło CSV: detekcja encodingu + delimitera, nagłówek przez wspólny
    ``find_similar_row_in_rows``, klucze lokalizacyjne, filtr ``banned_names``.
    CSV = zawsze JEDEN „arkusz" (``__xls_loc_sheet__ = 0``)."""

    def __init__(self, path, *, try_names=None, min_points=None, banned_names=None):
        self.path = path
        self.try_names = try_names
        self.min_points = min_points
        self.banned_names = (
            DEFAULT_BANNED_NAMES if banned_names is None else banned_names
        )

    @cached_property
    def _wiersze(self) -> list[list[str]]:
        with open(self.path, "rb") as f:
            tekst = _zdekoduj(f.read())
        delimiter = _wykryj_delimiter(tekst)
        # `newline=""` — kontrakt modułu `csv`: bez tego goły `\r` (końce linii
        # CR-only ze starych Maków / eksportów kadrowych albo zabłąkany `\r` po
        # ręcznej edycji) rzuca `_csv.Error: new-line character seen in unquoted
        # field` i wywala CAŁĄ analizę surowym tracebackiem. Z nim csv.reader
        # sam obsługuje wszystkie warianty końców linii wg dialektu.
        reader = csv.reader(io.StringIO(tekst, newline=""), delimiter=delimiter)
        return [list(r) for r in reader]

    @cached_property
    def _naglowek(self):
        res = find_similar_row_in_rows(
            self._wiersze, try_names=self.try_names, min_points=self.min_points
        )
        if res is None:
            raise HeaderNotFoundException("Nie znaleziono wiersza nagłówka w pliku CSV")
        return res

    @staticmethod
    def _pusty(row) -> bool:
        return not any((c or "").strip() for c in row)

    def liczba_arkuszy_z_danymi(self) -> int:
        # CSV to zawsze jeden „arkusz" — nigdy nie wyzwala reguły „jeden
        # arkusz = jeden import".
        return 1

    def count(self) -> int:
        _colnames, no = self._naglowek
        total = 0
        for n_row, row in enumerate(self._wiersze):
            if n_row < no:
                continue
            if self._pusty(row):
                continue
            total += 1
        return total

    def data(self) -> Iterator[dict]:
        colnames, no = self._naglowek
        colnames = rename_duplicate_columns(colnames)
        colnames.append("__xls_loc_sheet__")
        colnames.append("__xls_loc_row__")

        for n_row, row in enumerate(self._wiersze):
            if n_row < no:
                continue
            if self._pusty(row):
                continue
            data = list(row[: len(colnames) - 2])
            # CSV bywa „poszarpany": wiersz danych krótszy niż nagłówek.
            # openpyxl padduje do max_column, csv.reader NIE — bez dopadowania
            # zip() przesunąłby klucze lokalizacyjne na nazwy kolumn danych, a
            # __xls_loc_* nie powstałyby (→ TypeError w XLSParseError.__str__ i
            # NULL w sortowaniu get_details_set). Dopaduj do liczby kolumn danych:
            data += [""] * (len(colnames) - 2 - len(data))
            data.append(0)  # __xls_loc_sheet__ (CSV = jeden arkusz)
            data.append(n_row)  # __xls_loc_row__ (0-based, jak XLSImportFile)

            yld = dict(zip(colnames, data, strict=False))
            for banned_name in self.banned_names:
                yld.pop(banned_name, None)
            yield yld


def otworz_zrodlo(
    path, *, try_names=None, min_points=None, banned_names=None
) -> TabularSource:
    """Wykrywa format pliku (magic-bytes) i zwraca właściwe źródło —
    ``XLSXSource`` albo ``CSVSource`` — z tym samym kontraktem
    (``count()`` + ``data()``)."""
    klasa = XLSXSource if wykryj_format(path) == "xlsx" else CSVSource
    return klasa(
        path,
        try_names=try_names,
        min_points=min_points,
        banned_names=banned_names,
    )

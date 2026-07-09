"""Warstwa źródeł tabelarycznych dla importów (XLSX + CSV).

``TabularSource`` to wspólny protokół (``count()`` + ``data()``), którego
oczekuje pipeline importu. ``XLSXSource`` opakowuje istniejący
``XLSImportFile`` (openpyxl) bez zmian logiki parsowania. ``CSVSource``
(Task 3) dokłada obsługę CSV. ``otworz_zrodlo`` (Task 5) wykrywa format po
magic-bytes i zwraca właściwą implementację.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from .util import XLSImportFile


class TabularSource(Protocol):
    """Minimalny kontrakt konsumowany przez pipeline importu.

    ``data()`` MUSI emitować w każdym słowniku klucze lokalizacyjne
    ``__xls_loc_sheet__`` i ``__xls_loc_row__`` (kontrakt sortowania
    ``get_details_set``)."""

    def count(self) -> int: ...

    def data(self) -> Iterator[dict]: ...


class XLSXSource:
    """Adapter na istniejący ``XLSImportFile`` (openpyxl)."""

    def __init__(
        self, path, *, try_names=None, min_points=None, banned_names=None
    ):
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

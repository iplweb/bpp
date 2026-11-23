"""Czysty parser eksportu „Sources” serwisu Scopus (CiteScore) — FD#370.

Bez zależności od Django ORM. Obsługuje dwa warianty pliku:

- eksport wyników wyszukiwania źródeł: ``Source title``, ``CiteScore``,
  ``Highest percentile`` (tekst wieloliniowy: ``99.0%`` / pozycja / kategoria),
  ``SNIP``, ``SJR``, ``Publisher`` — **bez ISSN i bez roku**,
- wariant z kolumnami ISSN (``ISSN``/``Print ISSN``/``Print-ISSN`` oraz
  ``E-ISSN``/``EISSN``).

Roku w pliku nie ma — podaje go użytkownik w formularzu importu.
"""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from import_punktacji_zrodel.parser import _clean, _iter_rows_csv, _iter_rows_xlsx

_RE_PROCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
_RE_NIE_ALNUM = re.compile(r"[^a-z0-9]")

# Nagłówki po normalizacji (małe litery, same znaki alfanumeryczne).
_KOL_NAZWA = ("sourcetitle", "title")
_KOL_CITESCORE = ("citescore",)
_KOL_PERCENTYL = ("highestpercentile", "citescorehighestpercentile")
_KOL_ISSN = ("issn", "printissn", "pissn")
_KOL_EISSN = ("eissn", "electronicissn")
_KOL_SNIP = ("snip",)
_KOL_WYDAWCA = ("publisher",)


@dataclass
class CzasopismoScopus:
    nazwa: str
    issn: str | None = None
    e_issn: str | None = None
    citescore: Decimal | None = None
    percentyl: int | None = None
    snip: Decimal | None = None
    wydawca: str | None = None


def _norm_naglowek(v) -> str:
    return _RE_NIE_ALNUM.sub("", str(v or "").lower())


def _liczba(v) -> Decimal | None:
    s = _clean(v)
    if s is None:
        return None
    try:
        d = Decimal(s.replace(",", "."))
    except InvalidOperation:
        # Tekst zamiast liczby (np. „-”, „n/a”) = brak danych w tym wierszu.
        return None
    return d if d.is_finite() else None


def parsuj_citescore(v) -> Decimal | None:
    """CiteScore: liczba nieujemna, zaokrąglona do jednego miejsca."""
    d = _liczba(v)
    if d is None or d < 0:
        return None
    return d.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def parsuj_snip(v) -> Decimal | None:
    d = _liczba(v)
    if d is None or d < 0:
        return None
    return d.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def parsuj_percentyl(v) -> int | None:
    """Najwyższy percentyl jako liczba całkowita 0–100.

    Scopus eksportuje komórkę wieloliniową, np. ``"99.0%\\n1/428\\nOncology"``
    — bierzemy pierwszą liczbę ze znakiem ``%``. Komórka z samą liczbą
    (``87`` albo ``87.4``) też jest przyjmowana. Ułamki zaokrąglamy
    arytmetycznie; wartość spoza 0–100 to brak danych.
    """
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float, Decimal)):
        d = _liczba(v)
    else:
        m = _RE_PROCENT.search(str(v))
        d = _liczba(m.group(1)) if m else _liczba(v)
    if d is None:
        return None
    wynik = int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if not 0 <= wynik <= 100:
        return None
    return wynik


def parsuj_issn(v) -> str | None:
    """ISSN z komórki: Excel gubi zera wiodące (``00079235`` → ``79235``),
    a pełna lista Scopus podaje numery bez myślnika."""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = _clean(v)
    if s is None:
        return None
    s = s.replace(" ", "").upper()
    if s.isdigit() and len(s) < 8:
        s = s.zfill(8)
    return s


def _kolumna(naglowki: list[str], nazwy: tuple[str, ...]) -> int | None:
    for nazwa in nazwy:
        if nazwa in naglowki:
            return naglowki.index(nazwa)
    return None


def _znajdz_naglowek(rows: list[list]) -> tuple[int, list[str]]:
    for i, row in enumerate(rows):
        naglowki = [_norm_naglowek(c) for c in row]
        if (
            _kolumna(naglowki, _KOL_NAZWA) is not None
            and _kolumna(naglowki, _KOL_CITESCORE) is not None
        ):
            return i, naglowki
    raise ValueError(
        "To nie wygląda na eksport źródeł ze Scopus: nie znaleziono wiersza "
        "nagłówka z kolumnami „Source title” i „CiteScore”."
    )


def wczytaj_plik_scopus(path: str) -> list[CzasopismoScopus]:
    from import_common.util import sprawdz_plik_importu

    sprawdz_plik_importu(path)
    if path.lower().endswith(".csv"):
        rows = list(_iter_rows_csv(path))
    else:
        rows = list(_iter_rows_xlsx(path))

    hidx, naglowki = _znajdz_naglowek(rows)
    i_nazwa = _kolumna(naglowki, _KOL_NAZWA)
    i_cs = _kolumna(naglowki, _KOL_CITESCORE)
    i_pct = _kolumna(naglowki, _KOL_PERCENTYL)
    i_issn = _kolumna(naglowki, _KOL_ISSN)
    i_eissn = _kolumna(naglowki, _KOL_EISSN)
    i_snip = _kolumna(naglowki, _KOL_SNIP)
    i_wyd = _kolumna(naglowki, _KOL_WYDAWCA)

    def _cell(row, i):
        if i is None or i >= len(row):
            return None
        return row[i]

    wynik = []
    for row in rows[hidx + 1 :]:
        nazwa = _clean(_cell(row, i_nazwa))
        if nazwa is None:
            continue
        wynik.append(
            CzasopismoScopus(
                nazwa=nazwa,
                issn=parsuj_issn(_cell(row, i_issn)),
                e_issn=parsuj_issn(_cell(row, i_eissn)),
                citescore=parsuj_citescore(_cell(row, i_cs)),
                percentyl=parsuj_percentyl(_cell(row, i_pct)),
                snip=parsuj_snip(_cell(row, i_snip)),
                wydawca=_clean(_cell(row, i_wyd)),
            )
        )
    return wynik

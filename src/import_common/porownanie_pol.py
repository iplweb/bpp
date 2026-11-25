"""Jedno miejsce z regułami „czy dwie wartości pola publikacji to to samo”.

Korzysta z niego silnik porównania pól rekordu ze źródłem
(``importer_publikacji.wzbogacanie.pola``), a przez niego:

* wzbogacanie rekordu z CrossRef / PBN („Wzbogać z …” w module redagowania),
* komparator publikacji PBN (``komparator_publikacji_pbn``).

Każda funkcja sprowadza wartość do postaci, w której porównuje się ją
zwykłym ``==`` (pusty tekst = brak wartości).

``crossref_bpp.core.Komparator`` nie porównuje pól rekordu — WYSZUKUJE
w bazie BPP rekordy i pozycje słowników pasujące do wartości z CrossRef.
Wartości sprowadza tymi samymi funkcjami, na których stoją ``numer``
i ``doi`` (``import_common.normalization``); dopasowanie licencji silnik
bierze wprost z ``Komparator.porownaj_license``.
"""

import html
import re

from django.utils.html import strip_tags

from .normalization import normalize_doi, normalize_isbn


def odstepy(wartosc) -> str:
    """Tekst z odstępami sprowadzonymi do pojedynczych spacji."""
    return re.sub(r"\s+", " ", str(wartosc or "")).strip()


def tekst(wartosc) -> str:
    """Tekst bez znaczników HTML i nadmiarowych odstępów; encje HTML
    (``&amp;``, ``&nbsp;``…) zamienione na znaki."""
    return odstepy(html.unescape(strip_tags(str(wartosc or ""))))


def numer(wartosc) -> str:
    """ISSN / ISBN bez kresek, kropek i odstępów; znak kontrolny „X” bez
    rozróżniania wielkości liter."""
    if not isinstance(wartosc, str):
        return ""
    return (normalize_isbn(wartosc) or "").upper()


def doi(wartosc) -> str:
    """Sam numer DOI małymi literami — bez adresu doi.org i parametrów."""
    if not isinstance(wartosc, str):
        return ""
    return normalize_doi(wartosc) or ""


def strony(wartosc) -> str:
    """Zakres stron: łącznik, półpauza i pauza (z odstępami) to to samo."""
    return re.sub(r"\s*[-–—]\s*", "-", odstepy(wartosc))


def adres(wartosc) -> str:
    """Adres WWW bez końcowego ukośnika."""
    return odstepy(wartosc).rstrip("/")


def rok(wartosc) -> str:
    try:
        return str(int(wartosc))
    except (TypeError, ValueError):
        return ""

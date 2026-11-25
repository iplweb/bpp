"""Jedno miejsce z regułami „czy dwie wartości pola publikacji to to samo”.

Korzystają z niego:

* wzbogacanie rekordu z CrossRef / PBN (``importer_publikacji.wzbogacanie``),
* komparator publikacji PBN (``komparator_publikacji_pbn``).

``crossref_bpp.core.Komparator`` nie porównuje pól rekordu — WYSZUKUJE
w bazie BPP rekordy i pozycje słowników pasujące do wartości z CrossRef.
Wartości sprowadza tymi samymi funkcjami, na których stoją ``numer``
i ``doi`` (``import_common.normalization``); dopasowanie licencji
wzbogacanie bierze wprost z ``Komparator.porownaj_license``.

Każda funkcja sprowadza wartość do postaci, w której porównuje się ją
zwykłym ``==`` (pusty tekst = brak wartości).

Reguły WSPÓLNE dla wszystkich: ``numer`` (ISSN / ISBN), ``doi``.

Komparator publikacji PBN ma dla części pól reguły ZASTANE, dające inne
wyniki niż reguły wzbogacania. Są tu pod nazwami ``*_zastane`` i przypięte
testami charakteryzującymi (``komparator_publikacji_pbn/
test_charakteryzacja_porownania.py``). Ujednolicenie ich z regułami
wzbogacania zmienia wyniki komparatora, więc wymaga osobnej decyzji:

=========  ==============================  ===============================
pole       wzbogacanie                     komparator PBN (zastane)
=========  ==============================  ===============================
tytuł      bez znaczników HTML po obu      znaczniki usuwane tylko z BPP,
           stronach, odstępy sprowadzone   odstępy tylko na końcach
           do pojedynczych
DOI        ``doi`` — bez adresu doi.org    ``doi_zastane`` — sam numer,
           i parametrów, małe litery       małe litery (adres = inny DOI)
strony     ``strony`` — półpauza i         ``tekst_zastany`` — co do znaku
           odstępy wokół łącznika bez
           znaczenia
adres WWW  ``adres`` — bez końcowego „/”   ``tekst_zastany`` — co do znaku
tom, nr    ``tekst``                       ``tekst_zastany``
=========  ==============================  ===============================
"""

import re

from django.utils.html import strip_tags

from .normalization import normalize_doi, normalize_isbn


def odstepy(wartosc) -> str:
    """Tekst z odstępami sprowadzonymi do pojedynczych spacji."""
    return re.sub(r"\s+", " ", str(wartosc or "")).strip()


def tekst(wartosc) -> str:
    """Tekst bez znaczników HTML i nadmiarowych odstępów."""
    return odstepy(strip_tags(str(wartosc or "")))


def numer(wartosc) -> str:
    """ISSN / ISBN bez kresek, kropek i odstępów."""
    if not isinstance(wartosc, str):
        return ""
    return normalize_isbn(wartosc) or ""


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


# --- Reguły zastane komparatora publikacji PBN (patrz tabela wyżej) ---------


def tekst_zastany(wartosc) -> str:
    """Tekst co do znaku, bez odstępów na końcach."""
    return str(wartosc or "").strip()


def tytul_bpp_zastany(wartosc) -> str:
    """Tytuł rekordu BPP: bez znaczników HTML, bez odstępów na końcach."""
    return strip_tags(wartosc or "").strip()


def doi_zastane(wartosc) -> str:
    """DOI małymi literami, bez odstępów na końcach (adres zostaje)."""
    return str(wartosc or "").strip().lower()

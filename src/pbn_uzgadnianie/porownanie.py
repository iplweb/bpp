"""Porównanie rekordu BPP z wersją publikacji w PBN — TYLKO do raportu.

Uzgadnianie niczego w istniejącym rekordzie nie nadpisuje; ta lista mówi
redaktorowi, gdzie dane się rozjechały.
"""

import re

from django.utils.html import strip_tags

from bpp import const
from import_common.normalization import normalize_doi, normalize_isbn

_BIALE_ZNAKI = re.compile(r"\s+")


def _tekst(wartosc):
    return _BIALE_ZNAKI.sub(" ", strip_tags(str(wartosc or ""))).strip()


def _roznica(pole, bpp, pbn):
    return {"pole": pole, "bpp": str(bpp or ""), "pbn": str(pbn or "")}


def isbn_z_pbn(obiekt):
    return obiekt.get("isbn") or (obiekt.get("book") or {}).get("isbn")


def liczba_osob(obiekt, klucz):
    """Liczba osób w ``authors`` / ``editors`` obiektu PBN (dict albo lista)."""
    return len(obiekt.get(klucz) or ())


def liczba_osob_w_bpp(rekord, typ_ogolny):
    """Liczba powiązań rekordu BPP z osobami w danej roli (autor/redaktor)."""
    if not hasattr(rekord, "autorzy_set"):
        # Prace doktorskie/habilitacyjne mają jednego autora wprost w rekordzie.
        return 1 if typ_ogolny == const.TO_AUTOR else 0
    return rekord.autorzy_set.filter(
        typ_odpowiedzialnosci__typ_ogolny=typ_ogolny
    ).count()


def porownaj(rekord, obiekt):
    """Lista różnic między rekordem BPP (model źródłowy) a obiektem z PBN.

    Porównywane: tytuł, rok, DOI, ISBN (dla wydawnictw zwartych), adres WWW
    oraz liczba autorów i liczba redaktorów.
    """
    roznice = []

    tytul_bpp, tytul_pbn = _tekst(rekord.tytul_oryginalny), _tekst(obiekt.get("title"))
    if tytul_bpp.casefold() != tytul_pbn.casefold():
        roznice.append(_roznica("Tytuł", tytul_bpp, tytul_pbn))

    rok_pbn = obiekt.get("year") or (obiekt.get("book") or {}).get("year")
    if rok_pbn and str(rekord.rok) != str(rok_pbn):
        roznice.append(_roznica("Rok", rekord.rok, rok_pbn))

    doi_bpp = normalize_doi(getattr(rekord, "doi", None)) or ""
    doi_pbn = normalize_doi(obiekt.get("doi")) or ""
    if doi_bpp.lower() != doi_pbn.lower():
        roznice.append(_roznica("DOI", doi_bpp, doi_pbn))

    if hasattr(rekord, "isbn"):
        isbn_pbn = normalize_isbn(isbn_z_pbn(obiekt)) or ""
        isbny_bpp = {
            normalize_isbn(getattr(rekord, pole, None)) or ""
            for pole in ("isbn", "e_isbn")
        } - {""}
        if (isbn_pbn or isbny_bpp) and isbn_pbn not in isbny_bpp:
            roznice.append(_roznica("ISBN", ", ".join(sorted(isbny_bpp)), isbn_pbn))

    www_pbn = (obiekt.get("publicUri") or "").strip()
    www_bpp = {
        (getattr(rekord, pole, None) or "").strip() for pole in ("public_www", "www")
    } - {""}
    if (www_pbn or www_bpp) and www_pbn not in www_bpp:
        roznice.append(_roznica("Adres WWW", ", ".join(sorted(www_bpp)), www_pbn))

    for klucz, typ_ogolny, etykieta in (
        ("authors", const.TO_AUTOR, "Liczba autorów"),
        ("editors", const.TO_REDAKTOR, "Liczba redaktorów"),
    ):
        ile_bpp = liczba_osob_w_bpp(rekord, typ_ogolny)
        ile_pbn = liczba_osob(obiekt, klucz)
        if ile_bpp != ile_pbn:
            roznice.append(_roznica(etykieta, ile_bpp, ile_pbn))

    return roznice

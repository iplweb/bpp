"""Szukanie odpowiedników dla rekordów BPP bez powiązania z PBN.

Rekord BPP bez PBN UID to często nie „praca, której w PBN nie ma”, tylko:

* DUBEL — tę samą pracę wpisano ręcznie w BPP i osobno w PBN, a potem
  z PBN powstał w BPP drugi rekord (już z PBN UID);
* praca, która w PBN JEST (w lokalnej kopii danych PBN), ale żaden rekord
  BPP nie jest z nią powiązany.

Tu tylko je WSKAZUJEMY (raport); niczego nie scalamy ani nie wiążemy.

Dopasowanie: DOI (bez wielkości liter) albo tytuł + rok, gdzie tytuł jest
sprowadzany do samych liter i cyfr (bez znaczników HTML, wielkości liter,
interpunkcji i odstępów). Wszystko w pamięci, po stałej liczbie zapytań —
niezależnie od liczby rekordów.
"""

import html
import re

from django.utils.html import strip_tags
from pbn_client.const import DELETED

from bpp.models import Rekord
from import_common.normalization import normalize_doi, normalize_isbn
from pbn_api.models import Publication

PO_DOI = "ten sam DOI"
PO_ISBN = "ten sam ISBN"
PO_TYTULE = "ten sam tytuł i rok"

#: Krótsze klucze tytułu („Wstęp”, „Recenzja”) pasowałyby do zbyt wielu prac.
MIN_DLUGOSC_KLUCZA_TYTULU = 15

_NIE_LITERY_CYFRY = re.compile(r"[\W_]+", re.UNICODE)


def klucz_tytulu(tytul):
    """Tytuł sprowadzony do porównywalnej postaci (albo ``""``)."""
    tekst = html.unescape(strip_tags(str(tytul or "")))
    klucz = _NIE_LITERY_CYFRY.sub("", tekst.casefold())
    return klucz if len(klucz) >= MIN_DLUGOSC_KLUCZA_TYTULU else ""


def klucz_doi(doi):
    return (normalize_doi(doi) or "").lower()


class Indeks:
    """Słownik prac po DOI i po (tytuł, rok) — pierwsza wstawiona wygrywa."""

    def __init__(self):
        self.po_doi = {}
        self.po_tytule = {}

    def dodaj(self, wartosc, doi, tytul, rok):
        doi = klucz_doi(doi)
        if doi:
            self.po_doi.setdefault(doi, wartosc)
        tytul = klucz_tytulu(tytul)
        if tytul and rok:
            self.po_tytule.setdefault((tytul, int(rok)), wartosc)

    def znajdz(self, doi, tytul, rok):
        """``(wartość, po czym dopasowano)`` albo ``(None, "")``."""
        doi = klucz_doi(doi)
        if doi and doi in self.po_doi:
            return self.po_doi[doi], PO_DOI
        tytul = klucz_tytulu(tytul)
        if tytul and rok and (tytul, int(rok)) in self.po_tytule:
            return self.po_tytule[(tytul, int(rok))], PO_TYTULE
        return None, ""


def indeks_rekordow_bpp_z_pbn(rok_od, rok_do):
    """Rekordy BPP powiązane z PBN z danych lat (jedno zapytanie)."""
    indeks = Indeks()
    for rekord in (
        Rekord.objects.filter(rok__gte=rok_od, rok__lte=rok_do)
        .exclude(pbn_uid_id=None)
        .order_by("id")
    ):
        indeks.dodaj(rekord, rekord.doi, rekord.tytul_oryginalny, rekord.rok)
    return indeks


def indeks_niepowiazanych_publikacji_pbn(rok_od, rok_do):
    """Publikacje z lokalnej kopii PBN z danych lat, z którymi nie jest
    powiązany żaden rekord BPP (dwa zapytania)."""
    powiazane = set(
        Rekord.objects.exclude(pbn_uid_id=None).values_list("pbn_uid_id", flat=True)
    )
    indeks = Indeks()
    for pk, tytul, rok, doi in (
        Publication.objects.filter(year__gte=rok_od, year__lte=rok_do)
        .exclude(status=DELETED)
        .order_by("pk")
        .values_list("pk", "title", "year", "doi")
    ):
        if pk not in powiazane:
            indeks.dodaj(
                {"pbn_uid": pk, "tytul": tytul, "rok": rok, "doi": doi},
                doi,
                tytul,
                rok,
            )
    return indeks


def rekordy_bpp_uczelni(uczelnia, rok_od, rok_do):
    """Rekordy BPP, które powinny być na profilu instytucji w PBN.

    Z wybranych lat, o charakterze formalnym wysyłanym do PBN i z co
    najmniej jednym AFILIOWANYM autorem z jednostki tej uczelni. Rekord
    współautorski dwóch uczelni jednej instalacji należy więc do zakresu
    każdej z nich — celowo: każda powinna mieć go na własnym profilu.
    """
    return (
        Rekord.objects.filter(
            rok__gte=rok_od,
            rok__lte=rok_do,
            charakter_formalny__rodzaj_pbn__isnull=False,
            autorzy__jednostka__uczelnia=uczelnia,
            autorzy__afiliuje=True,
        )
        .distinct()
        .order_by("rok", "tytul_oryginalny", "id")
    )


def identyfikatory(rekord):
    """Klucze, po których da się zapytać PBN o pracę: ``["doi:…", "isbn:…"]``.

    ISBN tylko dla książek — rozdział nosi ISBN książki nadrzędnej, więc
    wskazywałby inną pracę.
    """
    klucze = []
    doi = klucz_doi(rekord.doi)
    if doi:
        klucze.append(f"doi:{doi}")
    if not getattr(rekord, "wydawnictwo_nadrzedne_id", None):
        for pole in ("isbn", "e_isbn"):
            isbn = normalize_isbn(getattr(rekord, pole, None))
            if isbn and f"isbn:{isbn}" not in klucze:
                klucze.append(f"isbn:{isbn}")
    return klucze

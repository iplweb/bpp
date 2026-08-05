"""Adapter: buduje realne słowniki tytułów/imion i callable ``probuj_match`` dla
czystego rdzenia ``parsers.osoba.rozbij_osobe`` (§7 spec).

Rdzeń zostaje czysty (testowalny z atrapami); ten moduł sięga do bazy i do
``znajdz_kandydatow_autora``. ``ParserKontekst`` budujemy RAZ na przebieg analizy
(``analizuj``) i wątkujemy do ``_przetworz_wiersz`` — nie per wiersz.
"""

from collections.abc import Callable
from dataclasses import dataclass

from bpp.models import Autor, Tytul
from import_common.core.autor import znajdz_kandydatow_autora

# Statyczne warianty zapisu tytułów (uzupełniane z realnych plików — §13 spec).
_TYTULY_STATYCZNE = {
    "dr",
    "dr hab.",
    "dr inż.",
    "dr n. med.",
    "dr hab. n. med.",
    "prof.",
    "prof. ucz.",
    "prof. dr hab.",
    "prof. dr hab. n. med.",
    "mgr",
    "mgr inż.",
    "inż.",
    "lek.",
    "lek. med.",
}

# Mała statyczna lista popularnych imion (uzupełniana z bazy w runtime).
_IMIONA_STATYCZNE = {
    "jan",
    "anna",
    "piotr",
    "maria",
    "andrzej",
    "katarzyna",
    "krzysztof",
    "małgorzata",
    "tomasz",
    "agnieszka",
    "paweł",
    "ewa",
    "michał",
    "adam",
    "magdalena",
    "marcin",
    "monika",
    "łukasz",
    "joanna",
    "jakub",
}


@dataclass(frozen=True)
class ParserKontekst:
    tytuly: set
    imiona_znane: set
    probuj_match: Callable[[str, str], bool]


def zbuduj_tytuly() -> set:
    """Słownik tytułów: skróty+nazwy z ``bpp.Tytul`` (lower) + statyka."""
    tytuly = set(_TYTULY_STATYCZNE)
    for skrot, nazwa in Tytul.objects.values_list("skrot", "nazwa"):
        if skrot:
            tytuly.add(skrot.strip().lower())
        if nazwa:
            tytuly.add(nazwa.strip().lower())
    return tytuly


def zbuduj_imiona_znane() -> set:
    """Znane imiona: tokeny z ``Autor.imiona`` (splitowane, lower) + statyka."""
    imiona = set(_IMIONA_STATYCZNE)
    for wartosc in Autor.objects.values_list("imiona", flat=True):
        if not wartosc:
            continue
        for token in wartosc.split():
            imiona.add(token.strip().lower())
    return imiona


def zbuduj_probuj_match() -> Callable[[str, str], bool]:
    """Fabryka ``probuj_match(imiona, nazwisko) -> bool`` opartego o
    ``znajdz_kandydatow_autora`` (jest kandydat = hipoteza kolejności trafia)."""

    def probuj(imiona: str, nazwisko: str) -> bool:
        return bool(znajdz_kandydatow_autora(imiona, nazwisko))

    return probuj


def zbuduj_parser_kontekst() -> ParserKontekst:
    """Buduje komplet zależności parsera RAZ (per przebieg analizy)."""
    return ParserKontekst(
        tytuly=zbuduj_tytuly(),
        imiona_znane=zbuduj_imiona_znane(),
        probuj_match=zbuduj_probuj_match(),
    )

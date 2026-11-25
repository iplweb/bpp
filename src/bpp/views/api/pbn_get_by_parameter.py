"""Szukanie rekordów PBN po DOI i po ISBN — strategie przycisku „Pobierz
z PBN” (``pbn_odpowiednik``) i akcji grupowej.

To NIE są widoki: dawne adresy „Pobierz po ISBN” / „Pobierz po DOI” zostały
usunięte w FD#515 (zastąpił je jeden widok ``api_get_pbn_by_identifiers``).
Została sama logika wyszukiwania — niczego nie wiąże.

Kolejność wyszukiwania (FD#622):

1. lokalnie — tabela publikacji pobranych z PBN oraz rekordy BPP, które mają
   już ustawiony odpowiednik w PBN. Najszybsze, bez sieci.
2. dopiero gdy lokalnie nic nie ma — API PBN, kolejno po kilku zapisach
   tego samego identyfikatora (PBN nie normalizuje zapytania: ISBN szukamy
   bez myślników i z myślnikami, w odmianie ISBN-13 i ISBN-10; DOI tak, jak
   go zapisano, i małymi literami).

Rok NIE zawęża wyników — ISBN i DOI to identyfikatory, a rok w PBN potrafi
różnić się od roku w BPP (np. rok książki zamiast roku rozdziału). Rok
służy wyłącznie do ustawienia kolejności kandydatów (w widoku).

Wersja sprzed FD#622 pytała PBN o jedną formę identyfikatora z filtrem roku,
a znalezione rekordy odrzucała, jeżeli nie dały się automatycznie dopasować
do jakiejś pracy w BPP (tytuł + rok) albo były już z którąś powiązane — np.
rozdział z ISBN-em książki kończył się komunikatem „Taka publikacja nie
istnieje", choć PBN ją miał. Przy okazji po cichu ustawiała odpowiednik
w PBN dopasowanym rekordom BPP.
"""

import functools
import itertools
import operator

import isbnlib
from django.db.models import Q

from bpp.models.cache import Rekord
from bpp.util.isbn import (
    adnotacje_isbn,
    kanoniczny_isbn,
    warianty_isbn,
    warunek_po_isbn,
    wyglada_jak_isbn,
)
from import_common.normalization import normalize_doi
from import_common.util import strip_doi_urls
from pbn_api.models import Publication
from pbn_integrator.utils import zapisz_mongodb

#: Ile rekordów maksymalnie zwracamy (i pobieramy z PBN) na jedno kliknięcie.
MAX_KANDYDATOW = 10


def formy_isbn(txt) -> list[str]:
    """Zapisy ISBN-u, o które pytamy PBN, w kolejności prób.

    Najpierw formy bez separatorów (ISBN-13 i ISBN-10 — PBN ich nie
    przelicza), potem te same z myślnikami według reguł ISBN, na końcu zapis
    dokładnie taki, jak wpisał użytkownik.
    """
    kanoniczne = warianty_isbn(txt)
    formy = list(kanoniczne)
    for wariant in kanoniczne:
        if not (isbnlib.is_isbn13(wariant) or isbnlib.is_isbn10(wariant)):
            # Zła suma kontrolna — nie wiadomo, gdzie postawić myślniki.
            continue
        try:
            z_myslnikami = isbnlib.mask(wariant)
        except isbnlib.NotValidISBNError:
            # Poprawny ISBN spoza znanych zakresów agencji ISBN.
            continue
        if z_myslnikami:
            formy.append(z_myslnikami)
    if kanoniczne:
        formy.append(txt.strip())
    return [f for f in dict.fromkeys(formy) if f]


def formy_doi(txt) -> list[str]:
    """Zapisy DOI, o które pytamy PBN: jak wpisano (bez prefiksu
    ``https://doi.org/``) oraz małymi literami."""
    if not isinstance(txt, str) or not txt.strip():
        return []
    formy = [strip_doi_urls(txt.strip().split("?")[0]), normalize_doi(txt)]
    return [f for f in dict.fromkeys(formy) if f]


class SzukaczPBN:
    """Strategia szukania rekordów PBN po jednym rodzaju identyfikatora."""

    #: Nazwa parametru wyszukiwania w API PBN (``isbn``, ``doi``).
    publication_element_name = None

    #: Nazwa identyfikatora w komunikatach dla użytkownika.
    nazwa_identyfikatora = None

    def formy(self, value) -> list[str]:
        """Zapisy identyfikatora, o które kolejno pytamy API PBN."""
        raise NotImplementedError

    def warunek_lokalny(self, value) -> Q:
        """Warunek na ``pbn_api.Publication`` dla wyszukiwania lokalnego."""
        raise NotImplementedError

    def rekordy_bpp(self, value):
        """Rekordy BPP z tym samym identyfikatorem (queryset ``Rekord``)."""
        raise NotImplementedError

    def szukaj_lokalnie(self, value) -> list[str]:
        """UID-y PBN znalezione bez odpytywania serwera PBN."""
        uidy = list(
            Publication.objects.filter(self.warunek_lokalny(value)).values_list(
                "pk", flat=True
            )[: MAX_KANDYDATOW * 2]
        )
        # Rekordy BPP, które mają już odpowiednik w PBN — np. książka
        # powiązana w BPP, której ISBN nosi też wprowadzany rozdział.
        uidy += list(
            self.rekordy_bpp(value)
            .exclude(pbn_uid_id=None)
            .values_list("pbn_uid_id", flat=True)[: MAX_KANDYDATOW * 2]
        )
        return list(dict.fromkeys(uidy))

    def szukaj_w_pbn(self, client, value) -> list[str]:
        """UID-y z API PBN. Formy identyfikatora próbujemy po kolei i kończymy
        na pierwszej, która cokolwiek zwróciła (każda próba to zapytanie
        sieciowe)."""
        for forma in self.formy(value):
            wyniki = client.search_publications(
                **{self.publication_element_name: forma}
            )
            uidy = [
                elem["mongoId"]
                for elem in itertools.islice(wyniki, MAX_KANDYDATOW)
                if isinstance(elem, dict) and elem.get("mongoId")
            ]
            if uidy:
                return list(dict.fromkeys(uidy))
        return []

    def zapewnij_lokalnie(self, client, uidy):
        """Pobierz z PBN rekordy, których nie ma jeszcze w lokalnej tabeli —
        wyszukiwarka pola „Odpowiednik w PBN" pokazuje tylko rekordy lokalne."""
        istniejace = set(
            Publication.objects.filter(pk__in=uidy).values_list("pk", flat=True)
        )
        for uid in uidy:
            if uid not in istniejace:
                zapisz_mongodb(client.get_publication_by_id(uid), Publication)


class SzukaczISBN(SzukaczPBN):
    publication_element_name = "isbn"
    nazwa_identyfikatora = "ISBN"

    def formy(self, value):
        return formy_isbn(value)

    def warunek_lokalny(self, value):
        # ``Publication.isbn`` przechowujemy bez separatorów, ale PBN dokleja
        # czasem dopiski („9788374307338 (druk)") — stąd ``icontains``
        # (indeks trigramowy na tej kolumnie), a nie równość. Element neutralny
        # ``Q(pk__in=[])`` chroni przed pustą listą wariantów.
        if not wyglada_jak_isbn(value):
            # Coś, co nie wygląda jak ISBN („brak", „83", fragment numeru) —
            # wyłącznie równość, inaczej ``icontains`` trafiłby w tysiące
            # rekordów.
            return Q(isbn=kanoniczny_isbn(value))
        return functools.reduce(
            operator.or_,
            (Q(isbn__icontains=wariant) for wariant in warianty_isbn(value)),
            Q(pk__in=[]),
        )

    def rekordy_bpp(self, value):
        warunek = warunek_po_isbn(value, "isbn", "e_isbn")
        if warunek is None:
            return Rekord.objects.none()
        return Rekord.objects.annotate(**adnotacje_isbn("isbn", "e_isbn")).filter(
            warunek
        )


class SzukaczDOI(SzukaczPBN):
    publication_element_name = "doi"
    nazwa_identyfikatora = "DOI"

    def formy(self, value):
        return formy_doi(value)

    def warunek_lokalny(self, value):
        # PBN zapisuje DOI z oryginalną wielkością liter („10.1016/B978-…"),
        # a redaktorzy wpisują różnie — porównujemy bez względu na wielkość.
        return Q(doi__iexact=normalize_doi(value))

    def rekordy_bpp(self, value):
        return Rekord.objects.filter(doi__iexact=normalize_doi(value))

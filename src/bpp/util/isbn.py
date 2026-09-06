"""Rozpoznawanie i normalizacja ISBN na potrzeby wyszukiwarek.

Dlaczego nie ``isbnlib.notisbn`` do rozpoznawania: ta funkcja liczy cyfrę
kontrolną, więc ISBN z literówką (albo po prostu błędny w danych źródłowych,
czego w PBN jest sporo) przestaje być rozpoznawany jako ISBN. Wyszukiwarka
klasyfikowała go wtedy jako tytuł i cicho nie znajdowała niczego. Do
*rozpoznania intencji użytkownika* suma kontrolna jest nam obojętna — liczy
się kształt wpisanego ciągu.

Sumy kontrolnej używamy natomiast tam, gdzie jest do czegoś potrzebna: przy
przeliczaniu ISBN-10 ↔ ISBN-13 (``warianty_isbn``), bo bez niej nie da się
policzyć poprawnego odpowiednika.
"""

import re

import isbnlib
from django.db.models import Q, TextField, Value
from django.db.models.functions import Replace, Upper

#: Znaki-separatory spotykane w zapisie ISBN. Poza myślnikiem ASCII także
#: półpauza i pauza — użytkownicy wklejają ISBN z Worda i z PDF-ów.
SEPARATORY = "-‐‑‒–—.  \t"

_USUWANE = str.maketrans("", "", SEPARATORY)

_ISBN_10 = re.compile(r"[0-9]{9}[0-9X]\Z")
#: ISBN-13 zaczyna się od prefiksu GS1 978 albo 979 — bez tego warunku każdy
#: trzynastocyfrowy ciąg (np. numer zamówienia) byłby brany za ISBN.
_ISBN_13 = re.compile(r"97[89][0-9]{10}\Z")


def kanoniczny_isbn(txt) -> str:
    """Zwróć ISBN bez separatorów, wielką literą X.

    Nie waliduje niczego — to czysta normalizacja zapisu.
    """
    if not txt or not isinstance(txt, str):
        return ""
    return txt.strip().translate(_USUWANE).upper()


def wyglada_jak_isbn(txt) -> bool:
    """Czy wpisany tekst ma kształt ISBN-u? BEZ walidacji sumy kontrolnej."""
    kanoniczny = kanoniczny_isbn(txt)
    return bool(_ISBN_10.match(kanoniczny) or _ISBN_13.match(kanoniczny))


def warianty_isbn(txt) -> list[str]:
    """Formy ISBN-u, po których warto szukać: kanoniczna + ISBN-13 + ISBN-10.

    Ani PBN, ani nasza baza nie przeliczają ISBN-10 na ISBN-13 — rekord
    zapisany w jednej formie nie znajdzie się po wpisaniu drugiej. Dlatego
    szukamy po obu. Gdy suma kontrolna jest błędna, ``isbnlib`` zwraca pusty
    ciąg i zostaje sama forma kanoniczna.
    """
    kanoniczny = kanoniczny_isbn(txt)
    if not kanoniczny:
        return []

    warianty = [kanoniczny]
    for konwersja in (isbnlib.to_isbn13, isbnlib.to_isbn10):
        inny = konwersja(kanoniczny)
        if inny and inny not in warianty:
            warianty.append(inny)
    return warianty


def isbn_znormalizowany(pole: str):
    """Wyrażenie ORM: wartość kolumny ``pole`` sprowadzona do formy kanonicznej.

    ISBN-y w BPP zapisywane są tak, jak wpisał je użytkownik — część z
    myślnikami, część bez. Porównanie musi więc normalizować obie strony;
    tu normalizujemy stronę bazodanową.

    Pokrewne, ale NIE to samo: ``import_common.core.normalized_db_isbn``
    (używane przez wyszukiwarkę globalną). Tamto wyrażenie ma zaszytą nazwę
    kolumny ``isbn`` (więc nie obsłuży ``e_isbn``), zdejmuje wyłącznie myślnik
    i sprowadza do małych liter. Tutaj potrzebujemy formy parametryzowanej
    polem i zgodnej z ``kanoniczny_isbn`` po stronie Pythona.

    Uwaga wydajnościowa: takie porównanie nie użyje indeksu B-drzewa na
    kolumnie. Ścieżka ta uruchamia się tylko wtedy, gdy wpisany tekst wygląda
    jak ISBN, więc przy typowych rozmiarach tabeli wydawnictw jest to bez
    znaczenia. Przy setkach tysięcy rekordów właściwym rozwiązaniem byłby
    indeks funkcyjny na tym samym wyrażeniu.
    """
    # ``output_field`` jest konieczne: ISBN bywa u nas raz ``CharField``
    # (``bpp.Wydawnictwo_Zwarte``), a raz ``TextField`` (``pbn_api.Publication``),
    # i bez tego Django odmawia złożenia wyrażenia z ``Value("")``.
    tekst = TextField()
    wyrazenie = pole
    for znak in SEPARATORY:
        wyrazenie = Replace(
            wyrazenie,
            Value(znak, output_field=tekst),
            Value("", output_field=tekst),
            output_field=tekst,
        )
    return Upper(wyrazenie, output_field=tekst)


def filtruj_tytul_lub_isbn(qs, txt, pole_tytulu, *pola_isbn):
    """Zawęź ``qs`` do rekordów pasujących tytułem albo — gdy ``txt`` wygląda
    jak ISBN — którymkolwiek z podanych pól ISBN.

    Warunki łączymy przez OR, a nie rozgałęziamy: wpisany ISBN praktycznie
    nigdy nie wystąpi w tytule, więc dołożenie warunku po tytule nic nie
    kosztuje, a ratuje rekordy z ISBN-em wklejonym w niewłaściwe pole.
    Adnotacja normalizująca powstaje wyłącznie na ścieżce ISBN-owej.
    """
    warunek = Q(**{f"{pole_tytulu}__icontains": txt})

    if wyglada_jak_isbn(txt):
        adnotacje = {
            f"_isbn_norm_{pole}": isbn_znormalizowany(pole) for pole in pola_isbn
        }
        qs = qs.annotate(**adnotacje)
        warianty = warianty_isbn(txt)
        for nazwa in adnotacje:
            warunek |= Q(**{f"{nazwa}__in": warianty})

    return qs.filter(warunek)

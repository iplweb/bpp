"""Matchery dla słownikowych encji: Wydzial, Tytul, Funkcja_Autora,
Grupa_Pracownicza, Wymiar_Etatu.

Wszystkie te funkcje próbują zmapować luźny napis na rekord w bazie po
nazwie/skrócie/aliasie.
"""

from django.db.models import Q

from bpp.models import (
    Funkcja_Autora,
    Grupa_Pracownicza,
    Jednostka,
    Tytul,
    Wymiar_Etatu,
)

from ..normalization import (
    normalize_funkcja_autora,
    normalize_grupa_pracownicza,
    normalize_tytul_naukowy,
    normalize_wymiar_etatu,
)


def matchuj_wydzial(nazwa: str | None):
    """Dobiera jednostkę TOP-LEVEL (rolę dawnego wydziału) po nazwie.

    Faza C (#438): model ``Wydzial`` znika — „wydział" to jednostka z
    ``parent IS NULL``. Match po ``nazwa`` LUB ``poprzednie_nazwy``: promowany
    1-jednostkowy wydział (0457) ma nazwę realnej jednostki, a dawną nazwę
    wydziału wnosi backfill (0466) do ``poprzednie_nazwy``. Zwraca
    ``Jednostka | None``.
    """
    if nazwa is None:
        return

    nazwa = nazwa.strip()
    if not nazwa:
        # Pusty string (np. pusta kolumna XLS → "") NIE może matchować —
        # ``poprzednie_nazwy__icontains=""`` = ``LIKE '%%'`` złapałby losowy
        # root. Zwracamy None, żeby wołający zawęził "po niczym" (DoesNotExist).
        return

    roots = Jednostka.objects.filter(parent__isnull=True)

    # ``Jednostka.nazwa`` jest globalnie unikatowa → exact match jest
    # jednoznaczny i ma priorytet nad dawną nazwą.
    exact = roots.filter(nazwa__iexact=nazwa).first()
    if exact is not None:
        return exact

    # Dawna nazwa wydziału (promowany 1-jednostkowy / lustro) siedzi w
    # ``poprzednie_nazwy`` (linie rozdzielone ``\n``, backfill 0466).
    # ``icontains`` to tani pre-filtr DB; dopasowanie po CAŁEJ linii
    # weryfikujemy w Pythonie — inaczej substring innej nazwy dałby
    # false-positive. ``order_by("pk")`` → determinizm przy wielu kandydatach.
    for root in roots.filter(poprzednie_nazwy__icontains=nazwa).order_by("pk"):
        if any(
            linia.strip().lower() == nazwa.lower()
            for linia in root.poprzednie_nazwy.splitlines()
        ):
            return root
    return None


def matchuj_tytul(tytul: str, create_if_not_exist=False) -> Tytul:
    """
    Dostaje tytuł: pełną nazwę albo skrót
    """

    try:
        return Tytul.objects.get(nazwa__iexact=tytul)
    except (Tytul.DoesNotExist, Tytul.MultipleObjectsReturned):
        return Tytul.objects.get(skrot=normalize_tytul_naukowy(tytul))


def matchuj_funkcja_autora(funkcja_autora: str) -> Funkcja_Autora:
    funkcja_autora = normalize_funkcja_autora(funkcja_autora)
    return Funkcja_Autora.objects.get(
        Q(nazwa__iexact=funkcja_autora) | Q(skrot__iexact=funkcja_autora)
    )


def matchuj_grupa_pracownicza(grupa_pracownicza: str) -> Grupa_Pracownicza:
    grupa_pracownicza = normalize_grupa_pracownicza(grupa_pracownicza)
    return Grupa_Pracownicza.objects.get(nazwa__iexact=grupa_pracownicza)


def matchuj_wymiar_etatu(wymiar_etatu: str) -> Wymiar_Etatu:
    wymiar_etatu = normalize_wymiar_etatu(wymiar_etatu)
    return Wymiar_Etatu.objects.get(nazwa__iexact=wymiar_etatu)

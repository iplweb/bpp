"""Matchery dla słownikowych encji: Wydzial, Tytul, Funkcja_Autora,
Grupa_Pracownicza, Wymiar_Etatu.

Wszystkie te funkcje próbują zmapować luźny napis na rekord w bazie po
nazwie/skrócie/aliasie.
"""

from django.db.models import Q

from bpp.models import (
    Funkcja_Autora,
    Grupa_Pracownicza,
    Tytul,
    Wydzial,
    Wymiar_Etatu,
)

from ..normalization import (
    normalize_funkcja_autora,
    normalize_grupa_pracownicza,
    normalize_tytul_naukowy,
    normalize_wymiar_etatu,
)


def matchuj_wydzial(nazwa: str | None):
    if nazwa is None:
        return

    try:
        return Wydzial.objects.get(nazwa__iexact=nazwa.strip())
    except Wydzial.DoesNotExist:
        pass


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

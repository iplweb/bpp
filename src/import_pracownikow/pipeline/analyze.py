"""Faza analizy (dry-run) importu pracowników.

``analizuj`` iteruje wiersze pliku XLS, matchuje jednostkę i autora istniejącym
API (``import_common.core``), ale **nie tworzy** brakujących słowników
(Funkcja_Autora / Grupa_Pracownicza / Wymiar_Etatu) ani powiązania
``Autor_Jednostka`` — to jest dry-run, więc nic nie jest zapisywane do domeny.
Brakujące dopasowania trafiają do ``row.diff_do_utworzenia`` (FK zostają
``None``), a właściwe utworzenie odbywa się dopiero w fazie integracji
(``import_pracownikow.pipeline.integrate``).
"""

from copy import copy

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from bpp.models import Autor_Jednostka, Jednostka, Tytul
from import_common.core import (
    matchuj_autora,
    matchuj_funkcja_autora,
    matchuj_grupa_pracownicza,
    matchuj_jednostke,
    matchuj_wymiar_etatu,
)
from import_common.exceptions import XLSMatchError, XLSParseError
from import_common.normalization import (
    normalize_funkcja_autora,
    normalize_grupa_pracownicza,
    normalize_nullboleanfield,
    normalize_wymiar_etatu,
)
from import_common.sources import otworz_zrodlo
from import_pracownikow.models import (
    AutorForm,
    ImportPracownikow,
    ImportPracownikowRow,
    JednostkaForm,
)
from import_pracownikow.parsers.wartosci import normalizuj_wartosci_wiersza


def _matchuj_slownik_lub_odroc(matcher, wartosc, normalizer, diff, klucz):
    """Zwraca dopasowany obiekt albo ``None``.

    Gdy słownik nie istnieje w bazie, NIE tworzy go (dry-run) — zapisuje
    znormalizowaną wartość do ``diff`` pod ``klucz``, żeby faza integracji
    wiedziała co utworzyć.
    """
    if not wartosc:
        return None
    try:
        return matcher(wartosc)
    except ObjectDoesNotExist:
        diff[klucz] = normalizer(wartosc)
        return None


def _matchuj_jednostke_lub_wyjatek(elem, jednostka_form):
    """Matchuje jednostkę, tłumacząc brak/wielość dopasowań na ``XLSMatchError``
    czytelny dla użytkownika (zamiast surowego tracebacku ORM-a)."""
    try:
        return matchuj_jednostke(
            jednostka_form.cleaned_data.get("nazwa_jednostki"),
            wydzial=jednostka_form.cleaned_data.get("wydział"),
        )
    except Jednostka.MultipleObjectsReturned:
        raise XLSMatchError(
            elem, "jednostka", "wiele dopasowań w systemie - po nazwie"
        ) from None
    except Jednostka.DoesNotExist:
        raise XLSMatchError(
            elem, "jednostka", "brak dopasowania w systemie - po nazwie"
        ) from None


def _przetworz_wiersz(parent, elem):
    dane_form = normalizuj_wartosci_wiersza(elem)
    jednostka_form = JednostkaForm(data=dane_form)
    jednostka_form.full_clean()
    if not jednostka_form.is_valid():
        raise XLSParseError(elem, jednostka_form, "weryfikacja nazwy jednostki")
    jednostka = _matchuj_jednostke_lub_wyjatek(elem, jednostka_form)

    autor_form = AutorForm(data=dane_form)
    autor_form.full_clean()
    if not autor_form.is_valid():
        raise XLSParseError(elem, autor_form, "weryfikacja danych autora")
    data = autor_form.cleaned_data
    tytul_str = data.get("tytuł_stopień")

    diff = {}
    funkcja = _matchuj_slownik_lub_odroc(
        matchuj_funkcja_autora,
        data.get("stanowisko"),
        normalize_funkcja_autora,
        diff,
        "funkcja_autora",
    )
    grupa = _matchuj_slownik_lub_odroc(
        matchuj_grupa_pracownicza,
        data.get("grupa_pracownicza"),
        normalize_grupa_pracownicza,
        diff,
        "grupa_pracownicza",
    )
    wymiar = _matchuj_slownik_lub_odroc(
        matchuj_wymiar_etatu,
        data.get("wymiar_etatu"),
        normalize_wymiar_etatu,
        diff,
        "wymiar_etatu",
    )

    autor = matchuj_autora(
        imiona=data.get("imię"),
        nazwisko=data.get("nazwisko"),
        jednostka=jednostka,
        bpp_id=data.get("bpp_id"),
        pbn_uid_id=data.get("pbn_uuid"),
        system_kadrowy_id=data.get("numer"),
        pbn_id=data.get("pbn_id"),
        orcid=data.get("orcid"),
        tytul_str=tytul_str,
    )
    if autor is None:
        raise XLSMatchError(elem, "autor", "brak dopasowania - różne kombinacje")
    if data.get("bpp_id") is not None and data.get("bpp_id") != autor.pk:
        raise XLSMatchError(
            elem,
            "autor",
            "BPP ID zmatchowanego autora i BPP ID w pliku XLS nie zgadzają się",
        )

    # Autor_Jednostka: dopasowanie bez tworzenia (dry-run).
    aj = Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).first()
    if aj is None:
        diff["autor_jednostka"] = {"autor": autor.pk, "jednostka": jednostka.pk}

    tytul = None
    if tytul_str:
        try:
            tytul = Tytul.objects.get(Q(nazwa=tytul_str) | Q(skrot=tytul_str))
        except Tytul.DoesNotExist:
            # tytuł opcjonalny — brak w słowniku nie blokuje analizy
            pass

    row = ImportPracownikowRow(
        parent=parent,
        dane_z_xls=elem,
        dane_znormalizowane=copy(autor_form.cleaned_data),
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        tytul=tytul,
        funkcja_autora=funkcja,
        grupa_pracownicza=grupa,
        wymiar_etatu=wymiar,
        podstawowe_miejsce_pracy=normalize_nullboleanfield(
            elem.get("podstawowe_miejsce_pracy")
        ),
        diff_do_utworzenia=diff,
        zmiany_potrzebne=False,
    )
    # Gdy AJ jeszcze nie istnieje, integracja i tak je utworzy — traktujemy
    # wiersz jako wymagający zmian. Gdy istnieje, liczymy normalnie.
    if aj is not None:
        # bool(diff): wiersz z odroczonym create'em słownika (stanowisko/
        # grupa/wymiar nieistniejące w bazie) MUSI trafić do integracji,
        # nawet gdy guard is-not-None wyzerował check (funkcja_autora=None
        # w analizie).
        row.zmiany_potrzebne = bool(diff) or row.check_if_integration_needed()
    else:
        row.zmiany_potrzebne = True
    row.save()


def analizuj(parent, p):
    zrodlo = otworz_zrodlo(parent.plik_xls.path)
    total = zrodlo.count()
    if total == 0:
        raise ValueError("Plik nie zawiera danych do importu (0 wierszy).")

    for elem in p.track(list(zrodlo.data()), total=total, label="Wczytywanie"):
        _przetworz_wiersz(parent, elem)

    parent.stan = ImportPracownikow.STAN_PRZEANALIZOWANY
    parent.save(update_fields=["stan"])

    wiersze = parent.get_details_set()
    p.result(
        {
            "total": wiersze.count(),
            "zmiany_potrzebne": parent.zmiany_potrzebne_set.count(),
            "byl_dry_run": True,
            "stan": parent.stan,
        }
    )

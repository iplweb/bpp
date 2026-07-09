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

from bpp.models import Autor_Jednostka, Jednostka, Tytul, Uczelnia
from import_common.core import (
    matchuj_autora,
    matchuj_funkcja_autora,
    matchuj_grupa_pracownicza,
    matchuj_jednostke,
    matchuj_wymiar_etatu,
)
from import_common.core.autor import znajdz_kandydatow_autora
from import_common.exceptions import XLSMatchError, XLSParseError
from import_common.normalization import (
    normalize_funkcja_autora,
    normalize_grupa_pracownicza,
    normalize_nullboleanfield,
    normalize_wymiar_etatu,
)
from import_common.sources import otworz_zrodlo
from import_pracownikow.mapping import MIN_POINTS, TRY_NAMES, remapuj_wiersz
from import_pracownikow.models import (
    AutorForm,
    ImportPracownikow,
    ImportPracownikowOdpiecie,
    ImportPracownikowRow,
    ImportPracownikowRowKandydat,
    JednostkaForm,
)
from import_pracownikow.parsers.leksykony import zbuduj_parser_kontekst
from import_pracownikow.parsers.osoba import rozbij_osobe
from import_pracownikow.parsers.wartosci import normalizuj_wartosci_wiersza
from import_pracownikow.pewnosc import (
    STATUS_TWARDY,
    STATUS_WIELU,
    oblicz_status_pewnosci,
    wybierz_autora_z_kandydatow,
)


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


def _dane_znormalizowane_z_parserem(cleaned_data, rozbicie):
    """Kopia cleaned_data wzbogacona o pewność rozbicia parsera (§7): confidence
    rozbicia (high/medium/low) i alternatywy trzymamy WEWNĄTRZ JSON, nie w
    kolumnie ``confidence`` (ta jest statusem dopasowania AUTORA — §8)."""
    dane = copy(cleaned_data)
    if rozbicie is not None:
        dane["parser_confidence"] = rozbicie.confidence
        dane["parser_alternatywy"] = rozbicie.alternatywy
    return dane


def _rozbij_osoba_sklejona(dane_form, parser_ctx):
    """Gdy jest ``parser_ctx`` i wiersz ma ``osoba_sklejona``, rozbija ją
    parserem (§7) i zasila brakujące imię/nazwisko/tytuł w ``dane_form``
    in-place. Zwraca wynik rozbicia (do zapisania confidence/alternatywy w
    ``dane_znormalizowane``) albo ``None``, gdy rozbicie nie zaszło."""
    if parser_ctx is None or not dane_form.get("osoba_sklejona"):
        return None
    rozbicie = rozbij_osobe(
        str(dane_form["osoba_sklejona"]),
        tytuly=parser_ctx.tytuly,
        imiona_znane=parser_ctx.imiona_znane,
        probuj_match=parser_ctx.probuj_match,
    )
    if not dane_form.get("nazwisko"):
        dane_form["nazwisko"] = rozbicie.nazwisko
    if not dane_form.get("imię"):
        dane_form["imię"] = rozbicie.imiona
    if rozbicie.tytul and not dane_form.get("tytuł_stopień"):
        dane_form["tytuł_stopień"] = rozbicie.tytul
    return rozbicie


def _dopasuj_tytul(tytul_str):
    """Zwraca ``Tytul`` po nazwie/skrócie albo ``None``. Tytuł jest opcjonalny —
    brak w słowniku nie blokuje analizy (dry-run)."""
    if not tytul_str:
        return None
    try:
        return Tytul.objects.get(Q(nazwa=tytul_str) | Q(skrot=tytul_str))
    except Tytul.DoesNotExist:
        return None


def _dopasuj_autora_i_status(data, jednostka, tytul_str):
    """Zwraca (autor, status, kandydaci). ID-path (priorytet) dopasowuje
    WYŁĄCZNIE po identyfikatorach: ``imiona/nazwisko/jednostka/tytul_str`` są
    PRZEKAZANE JAKO None, żeby ``matchuj_autora`` nie odpalił swoich fallbacków
    nazwiskowych/jednostkowych (autor.py:577-600). Inaczej remis top-tier byłby
    rozstrzygnięty jednostką/tytułem i błędnie oznaczony jako ``twardy`` —
    łamiąc §8 (jednostka/tytuł to tylko tie-breakery preselekcji, nie status).
    Gdy ID nie rozstrzyga (None) — SPADAMY do ścieżki kandydatów. Poza ID —
    status WPROST z ``znajdz_kandydatow_autora``; ``autor`` tylko dla
    twardy/zgadywanie (przez wspólny ``wybierz_autora_z_kandydatow``)."""
    ma_id = any(
        data.get(k) not in (None, "")
        for k in ("bpp_id", "orcid", "pbn_uuid", "numer", "pbn_id")
    )
    if ma_id:
        autor_po_id = matchuj_autora(
            imiona=None,
            nazwisko=None,
            jednostka=None,
            bpp_id=data.get("bpp_id"),
            pbn_uid_id=data.get("pbn_uuid"),
            system_kadrowy_id=data.get("numer"),
            pbn_id=data.get("pbn_id"),
            orcid=data.get("orcid"),
            tytul_str=None,
        )
        if autor_po_id is not None:
            return autor_po_id, STATUS_TWARDY, []

    kandydaci = znajdz_kandydatow_autora(data.get("imię"), data.get("nazwisko"))
    status = oblicz_status_pewnosci(kandydaci, match_po_id=False)
    autor = wybierz_autora_z_kandydatow(kandydaci, status)
    return autor, status, kandydaci


def _przetworz_wiersz(parent, elem, parser_ctx=None):
    dane_form = normalizuj_wartosci_wiersza(elem)
    rozbicie = _rozbij_osoba_sklejona(dane_form, parser_ctx)

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

    autor, status, kandydaci = _dopasuj_autora_i_status(data, jednostka, tytul_str)
    if (
        data.get("bpp_id") is not None
        and autor is not None
        and data.get("bpp_id") != autor.pk
    ):
        raise XLSMatchError(
            elem,
            "autor",
            "BPP ID zmatchowanego autora i BPP ID w pliku XLS nie zgadzają się",
        )

    # Autor_Jednostka: dopasowanie bez tworzenia (dry-run). Dla brak/wielu
    # (autor None) nie ma jak policzyć AJ — pomijamy.
    aj = None
    if autor is not None:
        aj = Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).first()
        if aj is None:
            diff["autor_jednostka"] = {"autor": autor.pk, "jednostka": jednostka.pk}

    tytul = _dopasuj_tytul(tytul_str)

    row = ImportPracownikowRow(
        parent=parent,
        dane_z_xls=elem,
        dane_znormalizowane=_dane_znormalizowane_z_parserem(
            autor_form.cleaned_data, rozbicie
        ),
        autor=autor,
        confidence=status,
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
    if autor is None:
        # brak/wielu: nie ma co integrować dopóki user nie rozstrzygnie
        row.zmiany_potrzebne = False
    elif aj is not None:
        # bool(diff): wiersz z odroczonym create'em słownika MUSI trafić do
        # integracji, nawet gdy guard is-not-None wyzerował check.
        row.zmiany_potrzebne = bool(diff) or row.check_if_integration_needed()
    else:
        row.zmiany_potrzebne = True
    row.save()

    if status == STATUS_WIELU:
        ImportPracownikowRowKandydat.zapisz_dla(row, kandydaci)


def _materializuj_odpiecia(parent):
    """Tworzy wiersze ``ImportPracownikowOdpiecie`` (zaznaczone=False) dla
    powiązań spoza pliku (§9). Delete-first → idempotentne względem re-analizy
    (``on_restart`` też je kasuje). Uczelnię ustala
    ``get_single_uczelnia_or_none`` (brak requestu w tle) — ``None`` pomija
    wykluczenie obcej jednostki. Zwraca liczbę utworzonych odpięć."""
    uczelnia = Uczelnia.objects.get_single_uczelnia_or_none()
    parent.odpiecia.all().delete()
    ImportPracownikowOdpiecie.objects.bulk_create(
        [
            ImportPracownikowOdpiecie(parent=parent, autor_jednostka=aj)
            for aj in parent.autorzy_spoza_pliku_set(uczelnia=uczelnia)
        ]
    )
    return parent.odpiecia.count()


def analizuj(parent, p):
    zrodlo = otworz_zrodlo(
        parent.plik_xls.path, try_names=TRY_NAMES, min_points=MIN_POINTS
    )
    total = zrodlo.count()
    if total == 0:
        raise ValueError("Plik nie zawiera danych do importu (0 wierszy).")

    mapowanie = parent.mapowanie_kolumn or {}
    parser_ctx = zbuduj_parser_kontekst()
    for elem in p.track(list(zrodlo.data()), total=total, label="Wczytywanie"):
        if mapowanie:
            elem = remapuj_wiersz(elem, mapowanie)
        _przetworz_wiersz(parent, elem, parser_ctx)

    liczba_odpiec = _materializuj_odpiecia(parent)

    parent.stan = ImportPracownikow.STAN_PRZEANALIZOWANY
    parent.save(update_fields=["stan"])

    wiersze = parent.get_details_set()
    p.result(
        {
            "total": wiersze.count(),
            "zmiany_potrzebne": parent.zmiany_potrzebne_set.count(),
            "odpiecia": liczba_odpiec,
            "byl_dry_run": True,
            "stan": parent.stan,
        }
    )

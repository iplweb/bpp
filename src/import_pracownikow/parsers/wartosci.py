"""Normalizacja wartości komórek nad warstwą źródła (CSV + XLSX).

CSV daje wartości jako stringi tam, gdzie XLSX (openpyxl) daje typy natywne
(``datetime`` dla dat). ``ExcelDateField`` obsługuje ``datetime`` i ISO
``YYYY-MM-DD``, ale nie polskie ``DD.MM.YYYY`` — tę lukę zamyka
``normalize_date_pl``. Warstwa jest specyficzna dla importu pracowników
(zna nazwy kolumn-dat), więc siedzi w ``import_pracownikow.parsers``, nie w
generycznym ``import_common``.
"""

from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from import_common.exceptions import XLSMatchError
from import_common.normalization import (
    kanonizuj_wymiar_etatu,
    parsuj_wymiar_etatu,
)

# Kolumny-daty w rygorystycznym schemacie Fazy 0/1 (nazwy = znormalizowane
# nagłówki wzorca BPP). Faza 2 (mapowanie) uczyni to konfigurowalnym.
_KLUCZE_DAT = ("data_zatrudnienia", "data_końca_zatrudnienia")


def normalize_date_pl(value):
    """datetime/date → ``date``; string ``DD.MM.YYYY`` → ``date``; wszystko
    inne (ISO, puste, nie-data) zwrócone bez zmian — walidację/odrzucenie
    zostawiamy ``ExcelDateField``. Kropka jednoznacznie sygnalizuje zapis
    europejski, więc nie kolidujemy z ``%m/%d/%Y`` z Django defaults."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s:
            try:
                return datetime.strptime(s, "%d.%m.%Y").date()
            except ValueError:
                # nie DD.MM.YYYY (może ISO, może śmieć) — zostaw formularzowi
                return value
    return value


def normalizuj_wartosci_wiersza(elem: dict) -> dict:
    """Zwraca KOPIĘ ``elem`` ze znormalizowanymi kolumnami-datami. Nie mutuje
    wejścia (audyt ``dane_z_xls`` musi zachować surowe wartości)."""
    out = dict(elem)
    for klucz in _KLUCZE_DAT:
        if out.get(klucz) is not None:
            out[klucz] = normalize_date_pl(out[klucz])
    return out


def _parsuj_wymiar_tolerancyjnie(surowa):
    """``parsuj_wymiar_etatu``, ale nieparsowalna forma → ``None`` zamiast
    wyjątku. Nieliczbowy wpis (np. „brak" — legalna wartość słownika
    ``Wymiar_Etatu``) NIE jest błędem: traktujemy go jak „brak ułamka" i
    przekazujemy surowo dalej (patrz ``scal_wymiar_etatu``), a nie wywalamy
    importu."""
    try:
        return parsuj_wymiar_etatu(surowa)
    except ValueError:
        # Świadomie: nieparsowalny wymiar = legacy string do przekazania do
        # słownika (stara, tolerancyjna ścieżka), nie sytuacja błędna.
        return None


def scal_wymiar_etatu(dane: dict) -> dict:
    """Scala dwie kolumny wymiaru etatu („(tekst)" + „(ułamek)") w jeden string
    pod kluczem ``wymiar_etatu`` (konsumowany dalej przez ``AutorForm`` +
    ``matchuj_wymiar_etatu``). Reguły:

    - OBIE kolumny mają sparsowalny ułamek i RÓŻNIĄ się (po zaokrągleniu do 2
      miejsc) → ``XLSMatchError``: „ten sam wymiar zapisany niespójnie" — nie
      przyjmujemy takiego pliku (analiza fail-fast, komunikat wskazuje wiersz i
      obie wartości). To JEDYNY twardy błąd tej funkcji;
    - jest sparsowalny ułamek → zapis KANONICZNY (polski przecinek, minimalne
      cyfry), kolumna ułamkowa autorytatywna, tekst do walidacji;
    - żadna forma nie jest sparsowalnym ułamkiem (np. „brak", pusta) →
      zachowujemy starą, tolerancyjną ścieżkę: surową wartość przekazujemy do
      słownika bez zmian. Pojedynczą kolumnę AKCEPTUJEMY — nieparsowalna
      wartość NIE wywala całego importu.

    Mutuje i zwraca ``dane``."""
    tekst_raw = dane.pop("wymiar_etatu_tekst", None)
    ulamek_raw = dane.pop("wymiar_etatu_ulamek", None)
    tekst = _parsuj_wymiar_tolerancyjnie(tekst_raw)
    ulamek = _parsuj_wymiar_tolerancyjnie(ulamek_raw)
    if (
        tekst is not None
        and ulamek is not None
        and round(float(tekst), 2) != round(float(ulamek), 2)
    ):
        raise XLSMatchError(
            dane,
            "wymiar_etatu",
            f"Rozbieżny wymiar etatu: tekst {tekst_raw!r} (={float(tekst)}) "
            f"≠ ułamek {ulamek_raw!r} (={float(ulamek)})",
        )
    wybrany = ulamek if ulamek is not None else tekst
    if wybrany is not None:
        dane["wymiar_etatu"] = kanonizuj_wymiar_etatu(wybrany)
    else:
        # Żadna forma nie jest liczbą — nie kanonizujemy; przekazujemy surową
        # wartość jak przed rozdzieleniem kolumn (ułamek priorytetem).
        surowa = ulamek_raw if ulamek_raw not in (None, "") else tekst_raw
        if surowa not in (None, ""):
            dane["wymiar_etatu"] = surowa
    return dane


def sklej_drugie_imie(dane: dict) -> dict:
    """Scala kolumnę ``drugie_imię`` z ``imię`` w jedno pole (``Autor`` ma
    jedno ``imiona`` na wszystkie imiona, np. „Jan" + „Paweł" → „Jan Paweł").
    Mutuje i zwraca ``dane``. Po scaleniu USUWA klucz ``drugie_imię`` —
    ``AutorForm`` go nie zna, a cały downstream czyta wyłącznie ``imię``.

    ``str(...)`` bo XLSX (openpyxl) potrafi dać komórkę liczbową — ``.strip()``
    na ``int`` rzuciłby ``AttributeError`` ubijający całą analizę (faza analizy
    jest fail-fast, bez per-wierszowego handlera).

    Wywoływać PO ``_rozbij_osoba_sklejona`` (parser uzupełnia ``imię`` tylko
    gdy puste) — inaczej wiersz z ``osoba_sklejona`` + ``drugie_imię`` bez
    kolumny ``imię`` zgubiłby pierwsze imię z rozbicia."""
    drugie = str(dane.get("drugie_imię") or "").strip()
    if drugie:
        pierwsze = str(dane.get("imię") or "").strip()
        dane["imię"] = f"{pierwsze} {drugie}".strip()
    dane.pop("drugie_imię", None)
    return dane


def rozbij_nazwisko_imie(dane: dict) -> dict:
    """Deterministyczny split „Nazwisko Imię" (nazwisko-first): pierwszy token
    → ``nazwisko``, reszta → ``imię``. Uzupełnia tylko PUSTE pola. Mutuje i
    zwraca ``dane``; usuwa klucz ``nazwisko_imię`` (``AutorForm`` go nie zna).

    Ograniczenie: dwuczłonowe nazwiska bez łącznika nie są rozbijane (pierwszy
    token = całe nazwisko). ``Ciuka-Witrylak`` (łącznik = 1 token) działa.

    Edge: 1 token (np. ``{"nazwisko_imię": "Kowalski"}``) → ``imię=""`` — wiersz
    i tak trafi do ``AutorForm`` (puste ``imię`` obsłuży walidacja formularza).
    """
    combined = str(dane.get("nazwisko_imię") or "").strip()
    if combined:
        tokeny = combined.split()
        if tokeny:
            if not dane.get("nazwisko"):
                dane["nazwisko"] = tokeny[0]
            if not dane.get("imię"):
                dane["imię"] = " ".join(tokeny[1:])
    dane.pop("nazwisko_imię", None)
    return dane


def oczysc_email(dane: dict):
    """Łagodna walidacja e-maila (§11): mutuje ``dane["email"]`` na poprawny,
    znormalizowany adres (lower + strip) albo ``""``; zwraca komunikat
    ostrzeżenia (gdy adres był NIEPUSTY i niepoprawny) albo ``None``.

    Wołane PRZED ``AutorForm.full_clean()`` w analizie — dzięki temu zły adres
    NIGDY nie unieważnia formularza (analiza jest fail-fast: jeden
    ``XLSParseError`` z ``full_clean`` ubija cały run). ``str(...)`` bo XLSX
    (openpyxl) potrafi dać komórkę nietekstową. Adres > 128 znaków traktujemy
    jak niepoprawny (model ``Autor.email`` = ``EmailField(max_length=128)`` —
    dłuższy wywaliłby ``Autor.objects.create``). Nie rzuca (per-wiersz
    recovery)."""
    if "email" not in dane:
        return None
    surowy = str(dane.get("email") or "").strip()
    if not surowy:
        dane["email"] = ""
        return None
    kandydat = surowy.lower()
    if len(kandydat) > 128:
        dane["email"] = ""
        return "Pominięto zbyt długi adres e-mail (>128 znaków)."
    try:
        validate_email(kandydat)
    except ValidationError:
        dane["email"] = ""
        return f"Pominięto niepoprawny adres e-mail: „{surowy}”."
    dane["email"] = kandydat
    return None

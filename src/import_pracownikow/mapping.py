"""Silnik mapowania kolumn importu pracowników.

Auto-propozycja mapowania nagłówek pliku → pole systemowe (przez słownik
synonimów, wzorzec ``import_dyscyplin.guess_rodzaj``), walidacja oraz
remapowanie wiersza. Profile (``dopasuj_profil``) w części 2 (Task 3).
"""

POLE_POMIN = "__pomin__"

# Pola docelowe = klucze oczekiwane przez JednostkaForm/AutorForm + kompozyt
# osoba_sklejona (Faza 3 — parser §7 rozbija ją na imię/nazwisko/tytuł).
POLA_DOCELOWE = [
    ("nazwisko", "Nazwisko"),
    ("imię", "Imię"),
    ("osoba_sklejona", "Osoba (tytuł+imię+nazwisko w jednej komórce)"),
    ("nazwa_jednostki", "Nazwa jednostki"),
    ("wydział", "Wydział"),
    ("tytuł_stopień", "Tytuł / stopień"),
    ("stanowisko", "Stanowisko"),
    ("grupa_pracownicza", "Grupa pracownicza"),
    ("wymiar_etatu", "Wymiar etatu"),
    ("data_zatrudnienia", "Data zatrudnienia"),
    ("data_końca_zatrudnienia", "Data końca zatrudnienia"),
    ("podstawowe_miejsce_pracy", "Podstawowe miejsce pracy"),
    ("numer", "Numer (system kadrowy)"),
    ("orcid", "ORCID"),
    ("pbn_uuid", "PBN UUID"),
    ("bpp_id", "BPP ID"),
]

# Pola identyfikacyjne — mapowanie MUSI zawierać (nazwisko+imię LUB
# osoba_sklejona) ORAZ jednostkę (patrz waliduj_mapowanie).
_POLA_IDENTYFIKACJI = {"nazwisko", "imię"}
_POLE_JEDNOSTKA = "nazwa_jednostki"

# Synonimy: znormalizowany nagłówek pliku → pole docelowe. Znormalizowany tak
# jak robi to normalize_cell_header (lower, spacje/kropki/myślniki → "_").
_SYNONIMY = {
    "nazwisko": "nazwisko",
    "nazwiska": "nazwisko",
    "imię": "imię",
    "imie": "imię",
    "imiona": "imię",
    "osoba": "osoba_sklejona",
    "osoba_sklejona": "osoba_sklejona",
    "pracownik": "osoba_sklejona",
    "nazwisko_i_imię": "osoba_sklejona",
    "nazwisko_i_imie": "osoba_sklejona",
    "imię_i_nazwisko": "osoba_sklejona",
    "imie_i_nazwisko": "osoba_sklejona",
    "imię_nazwisko": "osoba_sklejona",
    "imie_nazwisko": "osoba_sklejona",
    "nazwa_jednostki": "nazwa_jednostki",
    "jednostka": "nazwa_jednostki",
    "jedn_org": "nazwa_jednostki",
    "jednostka_organizacyjna": "nazwa_jednostki",
    "komorka_organizacyjna": "nazwa_jednostki",
    "komórka_organizacyjna": "nazwa_jednostki",
    "zaklad": "nazwa_jednostki",
    "zakład": "nazwa_jednostki",
    "klinika": "nazwa_jednostki",
    "katedra": "nazwa_jednostki",
    "wydzial": "wydział",
    "wydział": "wydział",
    "tytuł_stopień": "tytuł_stopień",
    "tytul_stopien": "tytuł_stopień",
    "tytuł___stopień": "tytuł_stopień",  # „Tytuł / Stopień" (spacje wokół /)
    "tytul___stopien": "tytuł_stopień",
    "tytuł": "tytuł_stopień",
    "tytul": "tytuł_stopień",
    "stopień": "tytuł_stopień",
    "stopien": "tytuł_stopień",
    "stanowisko": "stanowisko",
    "grupa_pracownicza": "grupa_pracownicza",
    "grupa": "grupa_pracownicza",
    "wymiar_etatu": "wymiar_etatu",
    "etat": "wymiar_etatu",
    "wymiar": "wymiar_etatu",
    "data_zatrudnienia": "data_zatrudnienia",
    "data_końca_zatrudnienia": "data_końca_zatrudnienia",
    "data_konca_zatrudnienia": "data_końca_zatrudnienia",
    "podstawowe_miejsce_pracy": "podstawowe_miejsce_pracy",
    "numer": "numer",
    "orcid": "orcid",
    "pbn_uuid": "pbn_uuid",
    "pbn_uid": "pbn_uuid",
    "bpp_id": "bpp_id",
}

# Nazwy-kandydaci nagłówka dla ``otworz_zrodlo``. KLUCZOWE dla Fazy 2: fuzzy-
# detekcja nagłówka (``find_similar_row_in_rows``) domyślnie szuka ≥3 nazw z
# ``DEFAULT_COL_NAMES`` (kanonicznych). Plik z przemianowanymi kolumnami (np.
# „Jedn org") nigdy by nie trafił w te 3 → ``HeaderNotFoundException`` PRZED
# ekranem mapowania. Dając wszystkie warianty synonimów jako ``try_names`` +
# ``MIN_POINTS=2`` sprawiamy, że nagłówek z ≥2 rozpoznawalnymi kolumnami (a
# nazwisko+imię są niemal zawsze) jest znajdowany, a dopiero ekran mapowania
# rozstrzyga resztę. **Te same** ``try_names``/``min_points`` MUSZĄ iść do
# ``naglowki_i_probka`` (ekran) I do ``analizuj`` (analiza) — inaczej ekran
# przyjmie plik, którego analiza potem nie otworzy.
TRY_NAMES = sorted(set(_SYNONIMY.keys()))
MIN_POINTS = 2


def zaproponuj_mapowanie(naglowki):
    """Dla listy znormalizowanych nagłówków pliku zwraca słownik
    ``{naglowek: pole_docelowe_lub_POLE_POMIN}`` na podstawie synonimów."""
    return {h: _SYNONIMY.get(h, POLE_POMIN) for h in naglowki}


def waliduj_mapowanie(mapowanie):
    """Zwraca listę błędów (pusta = OK). Reguły:
    - identyfikacja osoby: musi być zmapowane (``nazwisko`` ORAZ ``imię``)
      ALBO ``osoba_sklejona`` — oraz zawsze ``nazwa_jednostki``;
    - żadne pole docelowe (poza ``POLE_POMIN``) nie może być użyte dwukrotnie."""
    bledy = []
    uzyte = [v for v in mapowanie.values() if v != POLE_POMIN]

    ma_nazwisko_imie = _POLA_IDENTYFIKACJI <= set(uzyte)
    ma_osobe = "osoba_sklejona" in uzyte
    if not (ma_nazwisko_imie or ma_osobe):
        bledy.append(
            "Brak identyfikacji osoby: zmapuj 'nazwisko' + 'imię' albo "
            "'osoba (sklejona)'."
        )
    if _POLE_JEDNOSTKA not in uzyte:
        bledy.append("Brak wymaganego pola: nazwa jednostki")

    for pole in set(uzyte):
        if uzyte.count(pole) > 1:
            bledy.append(f"Pole '{pole}' przypisane dwukrotnie (duplikat)")

    return bledy


# Klucze lokalizacyjne przechodzą przez remap bez zmian (kontrakt sortowania).
_KLUCZE_LOKALIZACJI = ("__xls_loc_sheet__", "__xls_loc_row__")


def remapuj_wiersz(elem, mapowanie):
    """Przepisuje klucze wiersza pliku na kanoniczne pola wg ``mapowanie``.
    Kolumny zmapowane na ``POLE_POMIN`` (lub bez wpisu) są pomijane. Klucze
    lokalizacyjne (``__xls_loc_*``) przechodzą bez zmian."""
    out = {}
    for klucz, wartosc in elem.items():
        if klucz in _KLUCZE_LOKALIZACJI:
            out[klucz] = wartosc
            continue
        cel = mapowanie.get(klucz, POLE_POMIN)
        if cel != POLE_POMIN:
            out[cel] = wartosc
    return out


def dopasuj_profil(naglowki):
    """Zwraca ``ProfilMapowania``, którego zbiór kluczy mapowania pokrywa
    ≥90% znormalizowanych nagłówków pliku (najlepsze pokrycie), albo ``None``.
    Import lokalny — moduł ``mapping`` bywa ładowany bez potrzeby ORM."""
    from import_pracownikow.models import ProfilMapowania

    zbior_naglowkow = set(naglowki)
    if not zbior_naglowkow:
        return None

    najlepszy = None
    najlepsze_pokrycie = 0.0
    for profil in ProfilMapowania.objects.all():
        klucze = set(profil.mapowanie.keys())
        if not klucze:
            continue
        pokrycie = len(zbior_naglowkow & klucze) / len(zbior_naglowkow)
        if pokrycie >= 0.9 and pokrycie > najlepsze_pokrycie:
            najlepszy = profil
            najlepsze_pokrycie = pokrycie
    return najlepszy

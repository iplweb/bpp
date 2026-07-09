"""Silnik mapowania kolumn importu pracowników.

Auto-propozycja mapowania nagłówek pliku → pole systemowe (przez słownik
synonimów, wzorzec ``import_dyscyplin.guess_rodzaj``), walidacja oraz
remapowanie wiersza. Profile (``dopasuj_profil``) w części 2 (Task 3).
"""

POLE_POMIN = "__pomin__"

# Pola docelowe = klucze oczekiwane przez JednostkaForm/AutorForm. Kompozyty
# (osoba_sklejona) NALEŻĄ do Fazy 3 — tu ich nie ma.
POLA_DOCELOWE = [
    ("nazwisko", "Nazwisko"),
    ("imię", "Imię"),
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

# Pola identyfikacyjne — mapowanie MUSI zawierać nazwisko+imię ORAZ jednostkę.
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
    - musi być zmapowane ``nazwisko``, ``imię`` oraz ``nazwa_jednostki``;
    - żadne pole docelowe (poza ``POLE_POMIN``) nie może być użyte dwukrotnie."""
    bledy = []
    uzyte = [v for v in mapowanie.values() if v != POLE_POMIN]

    brakujace = _POLA_IDENTYFIKACJI - set(uzyte)
    if brakujace:
        bledy.append(
            "Brak wymaganych pól identyfikacji: " + ", ".join(sorted(brakujace))
        )
    if _POLE_JEDNOSTKA not in uzyte:
        bledy.append("Brak wymaganego pola: nazwa jednostki")

    for pole in set(uzyte):
        if uzyte.count(pole) > 1:
            bledy.append(f"Pole '{pole}' przypisane dwukrotnie (duplikat)")

    return bledy

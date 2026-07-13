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
    ("drugie_imię", "Drugie imię"),
    ("osoba_sklejona", "Osoba (tytuł+imię+nazwisko w jednej komórce)"),
    ("nazwisko_imię", "Nazwisko i imię (jedna komórka, nazwisko-first)"),
    ("nazwa_jednostki", "Nazwa jednostki"),
    ("nazwa_jednostki_niepelna", "Niepełna nazwa jednostki"),
    ("komórka_złożona", "Komórka (skrót + nazwa + oddział + znacznik)"),
    ("wydział", "Wydział"),
    ("tytuł_stopień", "Tytuł / stopień naukowy (np. dr, dr hab, prof, etc)"),
    ("stopień_służbowy", "Stopień służbowy (np. major, kapitan, etc)"),
    ("stanowisko", "Funkcja w jednostce"),
    ("stanowisko_dydaktyczne", "Stanowisko dydaktyczne"),
    ("grupa_pracownicza", "Grupa pracownicza"),
    ("wymiar_etatu_tekst", "Wymiar etatu (tekst)"),
    ("wymiar_etatu_ulamek", "Wymiar etatu (ułamek)"),
    ("data_zatrudnienia", "Data zatrudnienia"),
    ("data_końca_zatrudnienia", "Data końca zatrudnienia"),
    ("podstawowe_miejsce_pracy", "Podstawowe miejsce pracy"),
    ("numer", "Numer (system kadrowy)"),
    ("email", "E-mail"),
    ("orcid", "ORCID"),
    ("pbn_uuid", "PBN UUID"),
    ("bpp_id", "BPP ID"),
]

# Pola identyfikacyjne — mapowanie MUSI zawierać (nazwisko+imię LUB
# osoba_sklejona LUB nazwisko_imię) ORAZ jednostkę (nazwa_jednostki /
# nazwa_jednostki_niepelna / komórka_złożona — patrz waliduj_mapowanie).
_POLA_IDENTYFIKACJI = {"nazwisko", "imię"}

# Synonimy: znormalizowany nagłówek pliku → pole docelowe. Znormalizowany tak
# jak robi to normalize_cell_header (lower, spacje/kropki/myślniki → "_").
_SYNONIMY = {
    "nazwisko": "nazwisko",
    "nazwiska": "nazwisko",
    "imię": "imię",
    "imie": "imię",
    "imiona": "imię",
    "drugie_imię": "drugie_imię",
    "drugie_imie": "drugie_imię",
    "drugie_imiona": "drugie_imię",
    "imię_drugie": "drugie_imię",
    "imie_drugie": "drugie_imię",
    "osoba": "osoba_sklejona",
    "osoba_sklejona": "osoba_sklejona",
    "pracownik": "osoba_sklejona",
    "nazwisko_i_imię": "osoba_sklejona",
    "nazwisko_i_imie": "osoba_sklejona",
    "imię_i_nazwisko": "osoba_sklejona",
    "imie_i_nazwisko": "osoba_sklejona",
    "imię_nazwisko": "osoba_sklejona",
    "imie_nazwisko": "osoba_sklejona",
    "drugie": "drugie_imię",
    "nazwa_jednostki": "nazwa_jednostki",
    "jednostka": "nazwa_jednostki",
    "afiliacja": "nazwa_jednostki",
    "afiliacje": "nazwa_jednostki",
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
    "stopień_służbowy": "stopień_służbowy",
    "stopien_sluzbowy": "stopień_służbowy",
    "stopień_pożarniczy": "stopień_służbowy",
    "stopien_pozarniczy": "stopień_służbowy",
    "stanowisko": "stanowisko",
    "funkcja": "stanowisko",
    "funkcja_w_jednostce": "stanowisko",
    "stanowisko_dydakt": "stanowisko_dydaktyczne",
    "stanowisko_dydaktyczne": "stanowisko_dydaktyczne",
    "stanowisko_dyd": "stanowisko_dydaktyczne",
    "email": "email",
    "e_mail": "email",
    "mail": "email",
    "poczta": "email",
    "adres_email": "email",
    "nazwisko_imię": "nazwisko_imię",
    "nazwisko_imie": "nazwisko_imię",
    "komórka": "komórka_złożona",
    "komorka": "komórka_złożona",
    "komorka_zlozona": "komórka_złożona",
    "grupa_pracownicza": "grupa_pracownicza",
    "grupa": "grupa_pracownicza",
    "wymiar_etatu": "wymiar_etatu_tekst",
    "wymiar_etatu_2": "wymiar_etatu_ulamek",
    "etat": "wymiar_etatu_tekst",
    "wymiar": "wymiar_etatu_tekst",
    "data_zatrudnienia": "data_zatrudnienia",
    "data_od": "data_zatrudnienia",
    "data_do": "data_końca_zatrudnienia",
    "data_końca_zatrudnienia": "data_końca_zatrudnienia",
    "data_konca_zatrudnienia": "data_końca_zatrudnienia",
    "podstawowe_miejsce_pracy": "podstawowe_miejsce_pracy",
    "gł_zakład_pracy": "podstawowe_miejsce_pracy",
    "gl_zaklad_pracy": "podstawowe_miejsce_pracy",
    "główny_zakład_pracy": "podstawowe_miejsce_pracy",
    "glowny_zaklad_pracy": "podstawowe_miejsce_pracy",
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


def sprawdz_pojedynczy_arkusz(zrodlo):
    """Wymusza regułę „jeden arkusz = jeden import".

    Plik z więcej niż jednym arkuszem z danymi (np. dwie uczelnie w jednym
    skoroszycie — jak ``Pracownicy_..._UAFM_x_MWSL.xlsx``) jest ODRZUCANY:
    auto-sklejenie mieszałoby rozłączne zbiory, a auto-podział na osobne
    importy zakładałby, że arkusze są porównywalne (nie są — inne kolumny,
    inna uczelnia). Świadomie NIE obsługujemy plików wieloarkuszowych —
    użytkownik dzieli plik i importuje każdy arkusz osobno.

    Podnosi ``BadNoOfSheetsException`` z czytelnym komunikatem (ekran
    mapowania go łapie i pokazuje; w tle wyjątek trafia na konsolę/rollbar/
    admin). CSV to zawsze jeden arkusz — nigdy nie wyzwala tej reguły.
    """
    from import_common.exceptions import BadNoOfSheetsException

    n = zrodlo.liczba_arkuszy_z_danymi()
    if n > 1:
        raise BadNoOfSheetsException(
            f"Plik zawiera więcej niż jeden arkusz z danymi (znaleziono: {n}). "
            f"Jeden import obsługuje tylko jeden arkusz — podziel plik na osobne "
            f"pliki (po jednym arkuszu) i zaimportuj każdy osobno."
        )


# Fallback podłańcuchowy: gdy DOKŁADNY synonim nie trafił, sprawdzamy czy
# nagłówek ZAWIERA któryś fragment (kolejność = priorytet). Dla długich,
# opisowych nagłówków typu „stopien_tytul_aktualny_na_dzien_..." (IHIT).
# Ostrożnie: zbyt ogólny fragment daje fałszywe trafienia — auto-propozycja
# i tak jest korygowalna na ekranie mapowania.
_SYNONIMY_ZAWIERA = [
    ("afiliac", "nazwa_jednostki"),
    ("tytuł", "tytuł_stopień"),
    ("tytul", "tytuł_stopień"),
    ("stopień", "tytuł_stopień"),
    ("stopien", "tytuł_stopień"),
]


def _dopasuj_naglowek(h):
    """Pole docelowe dla znormalizowanego nagłówka: najpierw DOKŁADNY synonim,
    potem fallback podłańcuchowy, w ostateczności ``POLE_POMIN``."""
    cel = _SYNONIMY.get(h)
    if cel is not None:
        return cel
    for fragment, pole in _SYNONIMY_ZAWIERA:
        if fragment in h:
            return pole
    return POLE_POMIN


# Nagłówki (znormalizowane) traktowane jako „goły stopień" — rozstrzygane
# kontekstowo (patrz zaproponuj_mapowanie).
_GOLY_STOPIEN = {"stopień", "stopien"}


def zaproponuj_mapowanie(naglowki):
    """``{naglowek: pole_docelowe}`` na podstawie synonimów + reguła kontekstowa.

    Goły „stopień"/„stopien" jest DWUZNACZNY: gdy w pliku jest TAKŻE kolumna
    tytułu (inny nagłówek → ``tytuł_stopień``), goły stopień oznacza stopień
    SŁUŻBOWY; gdy nie ma tytułu — stopień NAUKOWY (``tytuł_stopień``). Inaczej
    dwie kolumny wpadłyby oba na ``tytuł_stopień`` → duplikat celu → walidacja
    odrzuca plik.
    """
    baza = {h: _dopasuj_naglowek(h) for h in naglowki}
    # Czy istnieje kolumna tytułu INNA niż sam goły stopień?
    ma_tytul = any(
        cel == "tytuł_stopień" and h not in _GOLY_STOPIEN for h, cel in baza.items()
    )
    for h in naglowki:
        if h in _GOLY_STOPIEN:
            baza[h] = "stopień_służbowy" if ma_tytul else "tytuł_stopień"
    return baza


def waliduj_mapowanie(mapowanie):
    """Zwraca listę błędów (pusta = OK). Reguły:
    - identyfikacja osoby: musi być zmapowane (``nazwisko`` ORAZ ``imię``)
      ALBO ``osoba_sklejona`` — oraz zawsze ``nazwa_jednostki``;
    - żadne pole docelowe (poza ``POLE_POMIN``) nie może być użyte dwukrotnie."""
    bledy = []
    uzyte = [v for v in mapowanie.values() if v != POLE_POMIN]

    ma_nazwisko_imie = _POLA_IDENTYFIKACJI <= set(uzyte)
    ma_osobe = "osoba_sklejona" in uzyte
    ma_nazwisko_imie_kol = "nazwisko_imię" in uzyte
    if not (ma_nazwisko_imie or ma_osobe or ma_nazwisko_imie_kol):
        bledy.append(
            "Brak identyfikacji osoby: zmapuj 'nazwisko' + 'imię', "
            "'osoba (sklejona)' albo 'nazwisko i imię (jedna komórka)'."
        )
    pola_jednostki = {"nazwa_jednostki", "nazwa_jednostki_niepelna", "komórka_złożona"}
    if not (pola_jednostki & set(uzyte)):
        bledy.append(
            "Brak jednostki: zmapuj 'nazwa jednostki', 'niepełna nazwa "
            "jednostki' albo 'komórka złożona'."
        )

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


def wybierz_profil_fallback(naglowki, prog=0.5):
    """NAJNOWSZY ostemplowany profil jako fallback — zwracany TYLKO gdy pokrywa
    ≥ ``prog`` swoich kluczy w nagłówkach pliku. Bierzemy WYŁĄCZNIE najnowszy
    (``order_by("-ostatnio_uzyty").first()``) i NIE schodzimy do starszych:
    chroni przed nałożeniem cudzego (np. z innej uczelni) profilu, którego
    reguła kontekstowa `stopień` §9 zostałaby zignorowana. Import lokalny (ORM
    lazy). Zwraca ``ProfilMapowania`` albo ``None``."""
    from import_pracownikow.models import ProfilMapowania

    zbior = set(naglowki)
    if not zbior:
        return None
    profil = (
        ProfilMapowania.objects.filter(ostatnio_uzyty__isnull=False)
        .order_by("-ostatnio_uzyty")
        .first()
    )
    if profil is None:
        return None
    klucze = set(profil.mapowanie.keys())
    if not klucze:
        return None
    pokrycie = len(zbior & klucze) / len(klucze)
    return profil if pokrycie >= prog else None

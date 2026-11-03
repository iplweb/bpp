"""Profil autora: rejestr sekcji + rozwiązywanie układu w PASY.

Podstrona autora to ciąg PASÓW: pas na całą szerokość albo para dwóch sekcji
obok siebie. Każda sekcja rejestru ma SZEROKOŚĆ (``"pol"`` / ``"cala"``);
pasy powstają z kolejności sekcji — dwie kolejne sekcje „pół” tworzą parę,
sekcja „cała” zaczyna nowy pas, a samotna „pół” (bez pary, np. bo sąsiad jest
pusty) rozciąga się na całą szerokość. Dzięki temu dziura po krótszej sekcji
może powstać najwyżej wewnątrz jednej pary, a nie na pół strony — jak przy
dwóch niezależnych kolumnach. Parowanie robi tag ``pasy_profilu`` dopiero po
wyrenderowaniu sekcji, więc puste sekcje nie zajmują połówki.

Administrator ustawia kolejność, szerokość, widoczność i (gdzie ma to sens)
limit pozycji — per-Uczelnia (system bywa multi-uczelniany). Układ trzymany
jest w ``Uczelnia.uklad_profilu_autora`` (JSON, lista pozycji ``{klucz,
szerokosc, widoczna, limit}``). Dodanie nowej sekcji to zmiana kodu, bez
migracji danych — ``rozwiaz_uklad`` dokleja sekcje nieobecne w zapisanej
konfiguracji z ich domyślnymi ustawieniami.

Back-compat: zapisy z czasów kolumn (``kolumna`` zamiast ``szerokosc``) i
klucze sekcji scalonych w grupy (np. ``biogram`` → ``wizytowka``) są
tolerowane — ``waliduj_uklad`` odrzuca nieznane klucze i uzupełnia brakującą
szerokość domyślną z katalogu.

Ten moduł jest czysty (nie importuje modeli), więc można go bezpiecznie używać
w formularzach i adminie. Budowanie danych sekcji (zapytania) jest w
``bpp.profil_autora_dane``.
"""

from dataclasses import dataclass

# --- Szerokości ------------------------------------------------------------

SZEROKOSC_POL = "pol"
SZEROKOSC_CALA = "cala"
SZEROKOSCI = (SZEROKOSC_POL, SZEROKOSC_CALA)

# --- Klucze sekcji: bloki szablonowe (bez buildera danych) ------------------

# Zdjęcie + biogram + opis — jedna karta „kim jest autor”.
KLUCZ_WIZYTOWKA = "wizytowka"
# Jednostka, historia zatrudnienia, dyscypliny, stopnie, identyfikatory —
# jedna karta; osobno byłyby to drobne karty parowane po dwie.
KLUCZ_AFILIACJA = "afiliacja"
KLUCZ_METRYKI = "metryki"
KLUCZ_RADON = "radon_osiagniecia"
KLUCZ_CYTOWANIA = "cytowania"
KLUCZ_WYSZUKIWARKA = "wyszukiwarka"
KLUCZ_RAPORT = "raport"
KLUCZ_EKSPORT = "eksport"

# --- Klucze sekcji: data-driven (builder w profil_autora_dane) --------------

KLUCZ_PODSUMOWANIE = "podsumowanie"
# Wykresy w latach (publikacje / punkty MNiSW / IF) — jeden pas, obok siebie.
KLUCZ_WYKRESY = "wykresy"
KLUCZ_STATYSTYKI_CHARAKTER = "statystyki_charakter"
KLUCZ_WSPOLAUTORZY = "wspolautorzy"
KLUCZ_NAJLEPSZE_PK = "najlepsze_pk"
KLUCZ_NAJLEPSZE_IF = "najlepsze_if"
KLUCZ_NAJNOWSZE_ARTYKULY = "najnowsze_artykuly"
KLUCZ_NAJNOWSZE_ZWARTE = "najnowsze_zwarte"
KLUCZ_OSTATNIO_EDYTOWANE = "ostatnio_edytowane"
KLUCZ_DYSCYPLINY = "dyscypliny"
KLUCZ_ZRODLA = "zrodla"
KLUCZ_PUNKTY_LATA = "punkty_lata"
KLUCZ_WYBRANE_PUBLIKACJE = "wybrane_publikacje"

# --- Limity list -----------------------------------------------------------

DOZWOLONE_LIMITY = (5, 10, 20, 30, 50)
DOMYSLNY_LIMIT = 10
# Listy prac stoją parami — krótkie (5), żeby pary miały podobną wysokość,
# a strona nie ciągnęła się ekranami list.
LIMIT_LIST_PRAC = 5


@dataclass(frozen=True)
class TypSekcji:
    klucz: str
    nazwa: str
    szerokosc: str = SZEROKOSC_POL
    ma_limit: bool = False
    # Domyślna liczba pozycji (tylko sekcje ``ma_limit``); także wartość
    # zastępcza, gdy zapisany limit jest spoza ``DOZWOLONE_LIMITY``.
    domyslny_limit: int = DOMYSLNY_LIMIT
    domyslnie_widoczna: bool = True
    # Sekcje „tylko-szablonowe” nie mają buildera danych (czytają ``autor`` /
    # ``uczelnia`` / ``raport_links`` z kontekstu strony). Nie są pomijane przy
    # braku danych — partial sam się bramkuje (``{% if %}``), a pusty wynik
    # renderowania odrzuca dopiero tag ``pasy_profilu``.
    template_only: bool = False
    # Czy sekcję owinąć kartą (tło + ramka, równa wysokość w parze). Bez karty:
    # sekcje, które same są „kartami” (kafle podsumowania, wyszukiwarka).
    karta: bool = True
    # Sekcja „cała”, która może też stanąć w połówce: gdy tuż przed nią
    # została samotna sekcja „pół” (np. afiliacja bez biogramu), dobiera się
    # do niej w parę zamiast zostawiać ją rozciągniętą na cały pas. Szablon
    # musi się dopasowywać do szerokości (wykresy: CSS grid auto-fit).
    elastyczna: bool = False

    @property
    def template(self):
        return f"browse/autor_sekcje/{self.klucz}.html"


# Kanoniczny porządek domyślny = domyślny układ strony (pary dobrane tak, by
# sąsiedzi mieli podobną wysokość). Dyscypliny / źródła / punkty w latach /
# wybrane publikacje istnieją w rejestrze, ale domyślnie są wyłączone.
KATALOG_SEKCJI = (
    TypSekcji(
        KLUCZ_PODSUMOWANIE,
        "Podsumowanie dorobku w bazie danych",
        SZEROKOSC_CALA,
        karta=False,
    ),
    TypSekcji(KLUCZ_WIZYTOWKA, "Zdjęcie i biogram", template_only=True),
    TypSekcji(KLUCZ_AFILIACJA, "Afiliacja i identyfikatory", template_only=True),
    TypSekcji(KLUCZ_WYKRESY, "Wykresy w latach", SZEROKOSC_CALA, elastyczna=True),
    TypSekcji(KLUCZ_STATYSTYKI_CHARAKTER, "Statystyki wg charakteru"),
    TypSekcji(KLUCZ_WSPOLAUTORZY, "Najczęstsi współautorzy", ma_limit=True),
    TypSekcji(KLUCZ_CYTOWANIA, "Cytowania", template_only=True),
    TypSekcji(KLUCZ_METRYKI, "Metryki ewaluacyjne", template_only=True),
    # RAD-on ładuje się w przeglądarce i przy braku danych zostaje ukryty —
    # na całą szerokość, żeby ukryty nie zostawiał pustej połówki pary.
    TypSekcji(
        KLUCZ_RADON,
        "Osiągnięcia (RAD-on)",
        SZEROKOSC_CALA,
        template_only=True,
        karta=False,
    ),
    TypSekcji(
        KLUCZ_WYSZUKIWARKA,
        "Wyszukiwarka prac",
        SZEROKOSC_CALA,
        template_only=True,
        karta=False,
    ),
    TypSekcji(KLUCZ_RAPORT, "Raport autora", template_only=True),
    TypSekcji(KLUCZ_EKSPORT, "Eksport publikacji", template_only=True),
    TypSekcji(
        KLUCZ_NAJLEPSZE_PK,
        "Najlepsze prace (punkty MNiSW)",
        ma_limit=True,
        domyslny_limit=LIMIT_LIST_PRAC,
    ),
    TypSekcji(
        KLUCZ_NAJLEPSZE_IF,
        "Najlepsze prace (Impact Factor)",
        ma_limit=True,
        domyslny_limit=LIMIT_LIST_PRAC,
    ),
    TypSekcji(
        KLUCZ_NAJNOWSZE_ARTYKULY,
        "Najnowsze artykuły",
        ma_limit=True,
        domyslny_limit=LIMIT_LIST_PRAC,
    ),
    TypSekcji(
        KLUCZ_NAJNOWSZE_ZWARTE,
        "Najnowsze książki / rozdziały",
        ma_limit=True,
        domyslny_limit=LIMIT_LIST_PRAC,
    ),
    TypSekcji(
        KLUCZ_OSTATNIO_EDYTOWANE,
        "Ostatnio edytowane",
        SZEROKOSC_CALA,
        ma_limit=True,
        domyslny_limit=LIMIT_LIST_PRAC,
    ),
    TypSekcji(KLUCZ_DYSCYPLINY, "Udział dyscyplin", domyslnie_widoczna=False),
    TypSekcji(
        KLUCZ_ZRODLA, "Najczęstsze źródła", ma_limit=True, domyslnie_widoczna=False
    ),
    TypSekcji(KLUCZ_PUNKTY_LATA, "Punkty / sloty w latach", domyslnie_widoczna=False),
    TypSekcji(
        KLUCZ_WYBRANE_PUBLIKACJE,
        "Wybrane publikacje",
        SZEROKOSC_CALA,
        domyslnie_widoczna=False,
    ),
)

KATALOG_WG_KLUCZA = {t.klucz: t for t in KATALOG_SEKCJI}


def domyslny_uklad():
    """Zwróć domyślny układ (lista pozycji) — wszystkie sekcje katalogu."""
    return [
        {
            "klucz": t.klucz,
            "szerokosc": t.szerokosc,
            "widoczna": t.domyslnie_widoczna,
            "limit": t.domyslny_limit if t.ma_limit else None,
        }
        for t in KATALOG_SEKCJI
    ]


def waliduj_uklad(dane):
    """Oczyść surową konfigurację z JSON-a do listy poprawnych pozycji.

    Każda pozycja wynikowa ma schemat ``{klucz, szerokosc, widoczna, limit}``.
    - Odrzuca nieznane i zduplikowane klucze.
    - Koryguje ``szerokosc`` do ``SZEROKOSCI``; brak / nieznana → domyślna
      z katalogu (back-compat dla zapisów z ``kolumna`` zamiast szerokości).
    - Koryguje ``limit`` do dozwolonego (lub ``None`` dla sekcji bez limitu).
    Zachowuje kolejność wejścia.
    """
    if not dane:
        return []

    wynik = []
    widziane = set()
    for pozycja in dane:
        if not isinstance(pozycja, dict):
            continue
        klucz = pozycja.get("klucz")
        typ = KATALOG_WG_KLUCZA.get(klucz)
        if typ is None or klucz in widziane:
            continue
        widziane.add(klucz)

        szerokosc = pozycja.get("szerokosc")
        if szerokosc not in SZEROKOSCI:
            szerokosc = typ.szerokosc

        widoczna = bool(pozycja.get("widoczna", True))

        if typ.ma_limit:
            limit = pozycja.get("limit")
            if limit not in DOZWOLONE_LIMITY:
                limit = typ.domyslny_limit
        else:
            limit = None

        wynik.append(
            {
                "klucz": klucz,
                "szerokosc": szerokosc,
                "widoczna": widoczna,
                "limit": limit,
            }
        )

    return wynik


def doklej_brakujace(zapisany):
    """Uzupełnij zapisany układ o sekcje katalogu, których w nim nie ma.

    Brakująca sekcja trafia ZA swojego najbliższego poprzednika z katalogu,
    który jest już w układzie; gdy takiego nie ma — na początek. Dzięki temu
    nowa sekcja nie ląduje na samym dole stron uczelni, które zapisały układ
    wcześniej.
    """
    domyslne_wg_klucza = {p["klucz"]: p for p in domyslny_uklad()}
    pozycje = list(zapisany)
    klucze = [p["klucz"] for p in pozycje]
    poprzednik = None
    for typ in KATALOG_SEKCJI:
        if typ.klucz not in klucze:
            idx = klucze.index(poprzednik) + 1 if poprzednik in klucze else 0
            pozycje.insert(idx, domyslne_wg_klucza[typ.klucz])
            klucze.insert(idx, typ.klucz)
        poprzednik = typ.klucz
    return pozycje


def rozwiaz_uklad(uczelnia):
    """Zwróć WIDOCZNE sekcje w docelowej kolejności renderowania.

    Czyta układ z ``uczelnia.uklad_profilu_autora`` (``uczelnia`` może być
    ``None`` — wtedy układ domyślny). Sekcje nieobecne w zapisanej
    konfiguracji dokleja ``doklej_brakujace`` z domyślnymi ustawieniami
    (forward-compat dla nowo dodanych typów sekcji).

    Zwraca listę pozycji ``{klucz, nazwa, template, szerokosc, limit,
    template_only, karta, elastyczna}``. Parowanie w pasy robi tag
    ``pasy_profilu``.
    """
    zapisany = waliduj_uklad(getattr(uczelnia, "uklad_profilu_autora", None))
    wynik = []
    for pozycja in doklej_brakujace(zapisany):
        if not pozycja["widoczna"]:
            continue
        typ = KATALOG_WG_KLUCZA[pozycja["klucz"]]
        wynik.append(
            {
                "klucz": typ.klucz,
                "nazwa": typ.nazwa,
                "template": typ.template,
                "szerokosc": pozycja["szerokosc"],
                "limit": pozycja["limit"],
                "template_only": typ.template_only,
                "karta": typ.karta,
                "elastyczna": typ.elastyczna,
            }
        )
    return wynik


def zloz_pasy(sekcje):
    """Pogrupuj wyrenderowane (niepuste) sekcje w pasy.

    ``sekcje`` to lista dictów z kluczem ``szerokosc``. Zwraca listę pasów;
    pas to lista 1 albo 2 sekcji. Dwie kolejne sekcje „pół” tworzą parę;
    sekcja „cała” stoi sama — chyba że jest ``elastyczna`` i tuż przed nią
    czeka samotna „pół”: wtedy tworzą parę. Samotna „pół” (bo następna jest
    zwykłą „całą” albo to koniec strony) stoi sama — i w szablonie zajmuje
    całą szerokość.
    """
    pasy = []
    czekajaca = None
    for sekcja in sekcje:
        if sekcja["szerokosc"] == SZEROKOSC_POL:
            if czekajaca is None:
                czekajaca = sekcja
            else:
                pasy.append([czekajaca, sekcja])
                czekajaca = None
            continue
        if czekajaca is not None and sekcja.get("elastyczna"):
            pasy.append([czekajaca, sekcja])
            czekajaca = None
            continue
        if czekajaca is not None:
            pasy.append([czekajaca])
            czekajaca = None
        pasy.append([sekcja])
    if czekajaca is not None:
        pasy.append([czekajaca])
    return pasy

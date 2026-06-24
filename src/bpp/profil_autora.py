"""Profil autora: rejestr sekcji OBU kolumn + rozwiązywanie układu.

Po rewizji „konfigurowalny układ obu kolumn" KAŻDY element podstrony autora
(zarówno dawniej-sztywne bloki LEWEJ kolumny, jak i konfigurowalne sekcje
PRAWEJ kolumny) jest pozycją rejestru otagowaną KOLUMNĄ (``"lewa"`` /
``"prawa"``). Administrator może przenieść dowolny blok (np. biogram albo
wyszukiwarkę) do drugiej kolumny, zmienić kolejność, ukryć go i (gdzie ma to
sens) ustawić limit pozycji — wszystko per-Uczelnia.

Układ jest GLOBALNY per-Uczelnia (system bywa multi-uczelniany): trzymany w
``Uczelnia.uklad_profilu_autora`` (JSON, lista pozycji ``{klucz, kolumna,
widoczna, limit}``). Dodanie nowej sekcji to zmiana kodu, bez migracji danych
— ``rozwiaz_uklad`` dokleja sekcje nieobecne w zapisanej konfiguracji z ich
domyślnymi ustawieniami (w ich domyślnej kolumnie).

Back-compat: stare konfiguracje (sprzed wprowadzenia kolumn) zawierają pozycje
bez ``kolumna``. ``waliduj_uklad`` uzupełnia brakującą kolumnę domyślną z
katalogu (dla dawnych sekcji prawej kolumny → ``"prawa"``), więc istniejące
zapisy działają bez zmian.

Ten moduł jest czysty (nie importuje modeli), więc można go bezpiecznie używać
w formularzach i adminie. Budowanie danych sekcji (zapytania) jest w
``bpp.profil_autora_dane``.
"""

from dataclasses import dataclass

# --- Kolumny ---------------------------------------------------------------

KOLUMNA_LEWA = "lewa"
KOLUMNA_PRAWA = "prawa"
KOLUMNY = (KOLUMNA_LEWA, KOLUMNA_PRAWA)

# --- Klucze sekcji: LEWA kolumna (dawniej sztywne bloki szablonu) -----------

KLUCZ_ZDJECIE = "zdjecie"
KLUCZ_BIOGRAM = "biogram"
KLUCZ_JEDNOSTKA = "jednostka"
KLUCZ_HISTORIA_ZATRUDNIENIA = "historia_zatrudnienia"
# Blok tożsamości „Dyscypliny naukowe" (aktualna/druga dyscyplina). Klucz
# CELOWO różny od statystycznej sekcji `dyscypliny` (udział dyscyplin) z prawej
# kolumny, żeby oba dało się włączyć równocześnie.
KLUCZ_DYSCYPLINY_NAUKOWE = "dyscypliny_naukowe"
KLUCZ_IDENTYFIKATORY = "identyfikatory"
KLUCZ_METRYKI = "metryki"
KLUCZ_STOPNIE = "stopnie"
KLUCZ_POPRZEDNIE_NAZWISKA = "poprzednie_nazwiska"
KLUCZ_OPIS = "opis"
KLUCZ_CYTOWANIA = "cytowania"
KLUCZ_WYSZUKIWARKA = "wyszukiwarka"
KLUCZ_RAPORT = "raport"
KLUCZ_EKSPORT = "eksport"

# --- Klucze sekcji: PRAWA kolumna (statystyki / wykresy / listy) ------------

KLUCZ_STATYSTYKI_CHARAKTER = "statystyki_charakter"
KLUCZ_WYKRES_LATA = "wykres_lata"
KLUCZ_WYKRES_PK_LATA = "wykres_pk_lata"
KLUCZ_WYKRES_IF_LATA = "wykres_if_lata"
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

DOZWOLONE_LIMITY = (10, 20, 30, 50)
DOMYSLNY_LIMIT = 10


@dataclass(frozen=True)
class TypSekcji:
    klucz: str
    nazwa: str
    kolumna: str = KOLUMNA_PRAWA
    ma_limit: bool = False
    domyslnie_widoczna: bool = True
    # Sekcje „tylko-szablonowe" nie mają buildera danych (czytają ``autor`` /
    # ``uczelnia`` / ``raport_links`` z kontekstu strony). Nie są pomijane przy
    # braku danych — partial sam się bramkuje (``{% if %}``).
    template_only: bool = False

    @property
    def template(self):
        return f"browse/autor_sekcje/{self.klucz}.html"


# Kanoniczny porządek domyślny. LEWA kolumna odwzorowuje DZISIEJSZY układ
# (wizytówka → tożsamość → wyszukiwarka → raport/eksport). PRAWA kolumna:
# statystyki/wykresy na górze, długi ogon list pod spodem; dyscypliny / źródła
# / punkty w latach / wybrane publikacje istnieją w rejestrze, ale domyślnie
# OFF. Domyślny układ MA renderować stronę zasadniczo tak jak dziś.
KATALOG_SEKCJI = (
    # --- LEWA kolumna (template-only: bez buildera danych) ---
    TypSekcji(KLUCZ_ZDJECIE, "Zdjęcie", KOLUMNA_LEWA, template_only=True),
    TypSekcji(KLUCZ_BIOGRAM, "Biogram", KOLUMNA_LEWA, template_only=True),
    TypSekcji(KLUCZ_JEDNOSTKA, "Aktualna jednostka", KOLUMNA_LEWA, template_only=True),
    TypSekcji(
        KLUCZ_HISTORIA_ZATRUDNIENIA,
        "Historia zatrudnienia",
        KOLUMNA_LEWA,
        template_only=True,
    ),
    TypSekcji(
        KLUCZ_DYSCYPLINY_NAUKOWE,
        "Dyscypliny naukowe",
        KOLUMNA_LEWA,
        template_only=True,
    ),
    TypSekcji(KLUCZ_IDENTYFIKATORY, "Identyfikatory", KOLUMNA_LEWA, template_only=True),
    TypSekcji(KLUCZ_METRYKI, "Metryki ewaluacyjne", KOLUMNA_LEWA, template_only=True),
    TypSekcji(KLUCZ_STOPNIE, "Stopnie naukowe", KOLUMNA_LEWA, template_only=True),
    TypSekcji(
        KLUCZ_POPRZEDNIE_NAZWISKA,
        "Poprzednie nazwiska",
        KOLUMNA_LEWA,
        template_only=True,
    ),
    TypSekcji(KLUCZ_OPIS, "Opis", KOLUMNA_LEWA, template_only=True),
    TypSekcji(KLUCZ_CYTOWANIA, "Cytowania", KOLUMNA_LEWA, template_only=True),
    TypSekcji(
        KLUCZ_WYSZUKIWARKA, "Wyszukiwarka prac", KOLUMNA_LEWA, template_only=True
    ),
    TypSekcji(KLUCZ_RAPORT, "Raport autora", KOLUMNA_LEWA, template_only=True),
    TypSekcji(KLUCZ_EKSPORT, "Eksport publikacji", KOLUMNA_LEWA, template_only=True),
    # --- PRAWA kolumna (data-driven: builder w profil_autora_dane) ---
    TypSekcji(KLUCZ_STATYSTYKI_CHARAKTER, "Statystyki wg charakteru", KOLUMNA_PRAWA),
    TypSekcji(KLUCZ_WYKRES_LATA, "Publikacje w latach", KOLUMNA_PRAWA),
    TypSekcji(KLUCZ_WYKRES_PK_LATA, "Punkty MNiSW w latach", KOLUMNA_PRAWA),
    TypSekcji(KLUCZ_WYKRES_IF_LATA, "Impact Factor w latach", KOLUMNA_PRAWA),
    TypSekcji(
        KLUCZ_WSPOLAUTORZY,
        "Najczęstsi współautorzy",
        KOLUMNA_PRAWA,
        ma_limit=True,
    ),
    TypSekcji(
        KLUCZ_NAJLEPSZE_PK,
        "Najlepsze prace (punkty MNiSW)",
        KOLUMNA_PRAWA,
        ma_limit=True,
    ),
    TypSekcji(
        KLUCZ_NAJLEPSZE_IF,
        "Najlepsze prace (Impact Factor)",
        KOLUMNA_PRAWA,
        ma_limit=True,
    ),
    TypSekcji(
        KLUCZ_NAJNOWSZE_ARTYKULY, "Najnowsze artykuły", KOLUMNA_PRAWA, ma_limit=True
    ),
    TypSekcji(
        KLUCZ_NAJNOWSZE_ZWARTE,
        "Najnowsze książki / rozdziały",
        KOLUMNA_PRAWA,
        ma_limit=True,
    ),
    TypSekcji(
        KLUCZ_OSTATNIO_EDYTOWANE, "Ostatnio edytowane", KOLUMNA_PRAWA, ma_limit=True
    ),
    TypSekcji(
        KLUCZ_DYSCYPLINY,
        "Udział dyscyplin",
        KOLUMNA_PRAWA,
        domyslnie_widoczna=False,
    ),
    TypSekcji(
        KLUCZ_ZRODLA,
        "Najczęstsze źródła",
        KOLUMNA_PRAWA,
        ma_limit=True,
        domyslnie_widoczna=False,
    ),
    TypSekcji(
        KLUCZ_PUNKTY_LATA,
        "Punkty / sloty w latach",
        KOLUMNA_PRAWA,
        domyslnie_widoczna=False,
    ),
    TypSekcji(
        KLUCZ_WYBRANE_PUBLIKACJE,
        "Wybrane publikacje",
        KOLUMNA_PRAWA,
        domyslnie_widoczna=False,
    ),
)

KATALOG_WG_KLUCZA = {t.klucz: t for t in KATALOG_SEKCJI}


def domyslny_uklad():
    """Zwróć domyślny układ (lista pozycji) — wszystkie sekcje katalogu."""
    return [
        {
            "klucz": t.klucz,
            "kolumna": t.kolumna,
            "widoczna": t.domyslnie_widoczna,
            "limit": DOMYSLNY_LIMIT if t.ma_limit else None,
        }
        for t in KATALOG_SEKCJI
    ]


def waliduj_uklad(dane):
    """Oczyść surową konfigurację z JSON-a do listy poprawnych pozycji.

    Każda pozycja wynikowa ma schemat ``{klucz, kolumna, widoczna, limit}``.
    - Odrzuca nieznane i zduplikowane klucze.
    - Koryguje ``kolumna`` do ``{"lewa", "prawa"}``; brak / nieznana →
      domyślna kolumna z katalogu (back-compat dla starych zapisów bez
      ``kolumna`` — dawne sekcje prawej kolumny dostają ``"prawa"``).
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

        kolumna = pozycja.get("kolumna")
        if kolumna not in KOLUMNY:
            kolumna = typ.kolumna

        widoczna = bool(pozycja.get("widoczna", True))

        if typ.ma_limit:
            limit = pozycja.get("limit")
            if limit not in DOZWOLONE_LIMITY:
                limit = DOMYSLNY_LIMIT
        else:
            limit = None

        wynik.append(
            {
                "klucz": klucz,
                "kolumna": kolumna,
                "widoczna": widoczna,
                "limit": limit,
            }
        )

    return wynik


def rozwiaz_uklad(uczelnia):
    """Zwróć WIDOCZNE sekcje obu kolumn w docelowej kolejności.

    Czyta globalny układ z ``uczelnia.uklad_profilu_autora`` (``uczelnia`` może
    być ``None`` — wtedy używany jest układ domyślny). Sekcje nieobecne w
    zapisanej konfiguracji dokleja na końcu — w ich DOMYŚLNEJ kolumnie — z
    domyślnymi ustawieniami (forward-compat dla nowo dodanych typów sekcji).

    Zwraca ``dict`` ``{"lewa": [...], "prawa": [...]}``; każda wartość to lista
    pozycji ``{klucz, nazwa, template, kolumna, limit, template_only}`` w
    kolejności renderowania.
    """
    zapisany = waliduj_uklad(getattr(uczelnia, "uklad_profilu_autora", None))
    klucze_zapisane = {p["klucz"] for p in zapisany}

    domyslne_wg_klucza = {p["klucz"]: p for p in domyslny_uklad()}
    pozycje = list(zapisany)
    for typ in KATALOG_SEKCJI:
        if typ.klucz not in klucze_zapisane:
            pozycje.append(domyslne_wg_klucza[typ.klucz])

    wynik = {KOLUMNA_LEWA: [], KOLUMNA_PRAWA: []}
    for pozycja in pozycje:
        if not pozycja["widoczna"]:
            continue
        typ = KATALOG_WG_KLUCZA[pozycja["klucz"]]
        wynik[pozycja["kolumna"]].append(
            {
                "klucz": typ.klucz,
                "nazwa": typ.nazwa,
                "template": typ.template,
                "kolumna": pozycja["kolumna"],
                "limit": pozycja["limit"],
                "template_only": typ.template_only,
            }
        )
    return wynik

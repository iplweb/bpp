"""Profil autora: rejestr sekcji PRAWEJ kolumny + rozwiązywanie układu.

Po rewizji 2-kolumnowej lewa kolumna podstrony autora jest STAŁA w szablonie
(zdjęcie, biogram, jednostka, historia zatrudnienia, identyfikatory,
wyszukiwarka, linki raportu). Konfigurowalny jest tylko porządek/widoczność
sekcji PRAWEJ kolumny, dlatego katalog (``KATALOG_SEKCJI``) obejmuje wyłącznie
te sekcje.

Układ jest GLOBALNY per-Uczelnia (system bywa multi-uczelniany): trzymany w
``Uczelnia.uklad_profilu_autora`` (JSON, lista pozycji ``{klucz, widoczna,
limit}``). Dzięki temu dodanie nowej sekcji to zmiana kodu, bez migracji danych
— ``rozwiaz_uklad`` dokleja sekcje nieobecne w zapisanej konfiguracji z ich
domyślnymi ustawieniami.

Ten moduł jest czysty (nie importuje modeli), więc można go bezpiecznie używać
w formularzach i adminie. Budowanie danych sekcji (zapytania) jest w
``bpp.profil_autora_dane``.
"""

from dataclasses import dataclass

# --- Klucze sekcji (prawa kolumna) -----------------------------------------

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
    ma_limit: bool = False
    domyslnie_widoczna: bool = True

    @property
    def template(self):
        return f"browse/autor_sekcje/{self.klucz}.html"


# Kanoniczny porządek domyślny PRAWEJ kolumny (§3.2 handoffa). Sekcje
# statystyk/wykresów na górze, długi ogon list pod spodem; dyscypliny / źródła
# / punkty w latach / wybrane publikacje istnieją w rejestrze, ale domyślnie
# OFF.
KATALOG_SEKCJI = (
    TypSekcji(KLUCZ_STATYSTYKI_CHARAKTER, "Statystyki wg charakteru"),
    TypSekcji(KLUCZ_WYKRES_LATA, "Publikacje w latach"),
    TypSekcji(KLUCZ_WYKRES_PK_LATA, "Punkty MNiSW w latach"),
    TypSekcji(KLUCZ_WYKRES_IF_LATA, "Impact Factor w latach"),
    TypSekcji(KLUCZ_WSPOLAUTORZY, "Najczęstsi współautorzy", ma_limit=True),
    TypSekcji(KLUCZ_NAJLEPSZE_PK, "Najlepsze prace (punkty MNiSW)", ma_limit=True),
    TypSekcji(KLUCZ_NAJLEPSZE_IF, "Najlepsze prace (Impact Factor)", ma_limit=True),
    TypSekcji(KLUCZ_NAJNOWSZE_ARTYKULY, "Najnowsze artykuły", ma_limit=True),
    TypSekcji(KLUCZ_NAJNOWSZE_ZWARTE, "Najnowsze książki / rozdziały", ma_limit=True),
    TypSekcji(KLUCZ_OSTATNIO_EDYTOWANE, "Ostatnio edytowane", ma_limit=True),
    TypSekcji(KLUCZ_DYSCYPLINY, "Udział dyscyplin", domyslnie_widoczna=False),
    TypSekcji(
        KLUCZ_ZRODLA, "Najczęstsze źródła", ma_limit=True, domyslnie_widoczna=False
    ),
    TypSekcji(KLUCZ_PUNKTY_LATA, "Punkty / sloty w latach", domyslnie_widoczna=False),
    TypSekcji(KLUCZ_WYBRANE_PUBLIKACJE, "Wybrane publikacje", domyslnie_widoczna=False),
)

KATALOG_WG_KLUCZA = {t.klucz: t for t in KATALOG_SEKCJI}


def domyslny_uklad():
    """Zwróć domyślny układ (lista pozycji) — wszystkie sekcje katalogu."""
    return [
        {
            "klucz": t.klucz,
            "widoczna": t.domyslnie_widoczna,
            "limit": DOMYSLNY_LIMIT if t.ma_limit else None,
        }
        for t in KATALOG_SEKCJI
    ]


def waliduj_uklad(dane):
    """Oczyść surową konfigurację z JSON-a do listy poprawnych pozycji.

    Odrzuca nieznane i zduplikowane klucze, koryguje limit do dozwolonego (lub
    ``None`` dla sekcji bez limitu). Zachowuje kolejność wejścia.
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

        widoczna = bool(pozycja.get("widoczna", True))

        if typ.ma_limit:
            limit = pozycja.get("limit")
            if limit not in DOZWOLONE_LIMITY:
                limit = DOMYSLNY_LIMIT
        else:
            limit = None

        wynik.append({"klucz": klucz, "widoczna": widoczna, "limit": limit})

    return wynik


def rozwiaz_uklad(uczelnia):
    """Zwróć listę WIDOCZNYCH sekcji prawej kolumny w docelowej kolejności.

    Czyta globalny układ z ``uczelnia.uklad_profilu_autora`` (``uczelnia`` może
    być ``None`` — wtedy używany jest układ domyślny). Sekcje nieobecne w
    zapisanej konfiguracji dokleja na końcu z domyślnymi ustawieniami
    (forward-compat dla nowo dodanych typów sekcji). Każda pozycja wynikowa
    zawiera ``klucz``, ``nazwa``, ``template`` i ``limit``.
    """
    zapisany = waliduj_uklad(getattr(uczelnia, "uklad_profilu_autora", None))
    klucze_zapisane = {p["klucz"] for p in zapisany}

    domyslne_wg_klucza = {p["klucz"]: p for p in domyslny_uklad()}
    pozycje = list(zapisany)
    for typ in KATALOG_SEKCJI:
        if typ.klucz not in klucze_zapisane:
            pozycje.append(domyslne_wg_klucza[typ.klucz])

    wynik = []
    for pozycja in pozycje:
        if not pozycja["widoczna"]:
            continue
        typ = KATALOG_WG_KLUCZA[pozycja["klucz"]]
        wynik.append(
            {
                "klucz": typ.klucz,
                "nazwa": typ.nazwa,
                "template": typ.template,
                "limit": pozycja["limit"],
            }
        )
    return wynik

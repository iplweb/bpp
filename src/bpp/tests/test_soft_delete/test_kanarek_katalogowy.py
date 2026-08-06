"""Kanarek katalogowy: KAŻDY widok czytający tabelę objętą soft-delete
MUSI zależeć od jej kolumny ``deleted_at`` — albo być na jawnej,
uzasadnionej liście wyjątków.

## Dlaczego ten test istnieje

Faza 01 odkrywała konsumentów surowych tabel ``*_autor`` **pojedynczo,
przez awarie**: najpierw bramka cache'u, potem bramka denorma,
``unique_together``, legacy constraint z 2018, a na końcu finalna recenzja
znalazła jeszcze trzy widoki pochodne (``liczba_autorow``, ranking,
rozbieżności) czytające surową tabelę zamiast już przefiltrowanego widoku
źródłowego. Każdy z nich to ta sama klasa błędu: coś czyta surową tabelę,
nie wiedząc o ``deleted_at``.

Faza 02 (soft-delete PUBLIKACJI) trafi na dokładnie ten sam problem dla
tabel ``bpp_wydawnictwo_ciagle`` / ``_zwarte`` / ``bpp_patent`` /
``bpp_praca_doktorska`` / ``bpp_praca_habilitacyjna``. Ten kanarek pilnuje
niezmiennika automatycznie, zamiast czekać na kolejną rundę odkryć przez
awarie.

## Źródło prawdy: ``pg_depend``, nie tekst definicji

Pierwsza wersja tego kanarka (patrz historia gita) sprawdzała obecność
podłańcucha ``"deleted_at" in definicja`` — GOŁY, NIEKWALIFIKOWANY
tabelą. Recenzja fazy 02 wykazała, że to daje FAŁSZYWĄ ZIELEŃ dokładnie
na tej klasie błędu, przed którą kanarek ma chronić: widok czytający
``bpp_wydawnictwo_ciagle`` (tabela publikacji, faza 02) ODZIEDZICZA
podłańcuch ``deleted_at`` z filtra po ``bpp_wydawnictwo_ciagle_autor``
(tabela through, faza 01, w tym samym ``JOIN``), mimo że wcale nie filtruje
po WŁASNYM ``deleted_at`` tabeli publikacji. Zweryfikowane na żywym
katalogu 2026-08-06: **trzy widoki na cztery** czytające
``bpp_wydawnictwo_ciagle`` przechodziłyby starym testem na zielono, mimo
braku filtra po tej tabeli (patrz ``kanarek-fix-report.md`` — tabela
przed/po).

Naprawa: zamiast szukać substringa w tekście, pytamy katalog Postgresa
``pg_depend``, czy widok FAKTYCZNIE zależy od KOLUMNY ``deleted_at``
KONKRETNEJ tabeli — dokładnie to samo narzędzie, którego migracje
``0433``/``0489``/``0494`` używają do budowy bramek ``WHEN`` (kolumny
bazowe referowane przez widok, na poziomie ``pg_rewrite`` → ``pg_depend``
→ ``pg_attribute``). Tej samej techniki (bez filtra po nazwie kolumny)
używamy też do wykrycia relacji „widok W czyta tabelę T" — ``pg_depend``
zamiast tekstu, więc znika też klasa pułapek tekstowych, których stary
matcher musiał unikać ręcznie: ``deleted_at`` w komentarzu SQL, w aliasie
kolumny, w cudzej kolumnie o tej samej nazwie.

``pg_views`` (schemat ``public``), na ŻYWEJ bazie, pozostaje źródłem
prawdy TYLKO dla testów sanity/mutacyjnego i dla symulacji „starego
algorytmu" (patrz niżej) — NIE dla rdzenia kanarka. Późniejsze migracje
nadpisują wcześniejsze definicje widoków (``CREATE OR REPLACE VIEW``),
więc treść ``.sql`` w katalogu migracji nie musi być tym, co faktycznie
stoi w bazie; ``baseline-sql/baseline.sql`` też zawodzi jako źródło — to
snapshot sprzed części migracji (sprawdzone: ``baseline.sql`` ma
``NULL::bigint AS liczba_autorow`` zamiast realnego ``count()`` z migracji
``0494``).

## Niezmiennik

Dla każdej pary (widok W, tabela T) takiej, że W czyta T (wg ``pg_depend``),
a T jest w ``TABELE_SOFT_DELETE`` — musi istnieć zależność W od kolumny
``T.deleted_at`` (wg ``pg_depend``), albo W jest na liście ``WYJATKI``.

## Wzorzec naprawy

- widok źródłowy (filtr ``WHERE deleted_at IS NULL`` po WŁASNEJ kolumnie
  tabeli) — ``src/bpp/migrations/0489_soft_delete_autorzy_views.py``;
- widok pochodny z agregatem po ``LEFT JOIN`` (``count()`` itp.) — UŻYJ
  ``FILTER (WHERE deleted_at IS NULL)``, NIE warunku w ``WHERE``/``JOIN``:
  ten drugi zamienia ``LEFT JOIN`` w efektywny ``INNER JOIN`` i wywala z
  widoku cały wiersz nadrzędny, któremu soft-deletowano WSZYSTKICH
  potomków — ``src/bpp/migrations/0494_liczba_autorow_bez_skasowanych.py``;
- widok pochodny z prostym ``WHERE``/``JOIN ... ON`` (bez agregatu) —
  dopisz warunek do ``WHERE`` —
  ``src/bpp/migrations/0495_nowe_sumy_bez_skasowanych.py``;
- helper do bezpiecznego dopisania warunku przez introspekcję (zamiast
  przepisywania SQL-a ręcznie, co rozjeżdża się przy zmianie kolumn) —
  ``src/bpp/migration_util.py`` (``viewdef``, ``widok_dopisz_warunek``,
  ``widok_usun_warunek``).

## Pułapka dopasowania tekstowego (funkcje ``widok_uzywa_tabeli`` niżej)

``widok_uzywa_tabeli``/``_regex_dla_tabeli`` (dopasowanie z granicą słowa)
NIE są już częścią rdzenia kanarka — ale zostają w module, bo:

1. ich własne testy (``test_matcher_...`` niżej) pilnują regresji samej
   klasy pułapki tekstowej (``bpp_wydawnictwo_ciagle_autor`` jest
   PREFIKSEM ``bpp_wydawnictwo_ciagle_autorzy``, i odwrotnie
   ``bpp_wydawnictwo_ciagle`` jest PREFIKSEM ``bpp_wydawnictwo_ciagle_autor``)
   — to dokumentacja tego, DLACZEGO w ogóle przesiedliśmy się na
   ``pg_depend``;
2. ``test_symulacja_fazy_02_...`` niżej używa ich do odtworzenia
   DOKŁADNIE starego (przed naprawą) algorytmu, żeby udowodnić, że
   naprawa faktycznie łapie to, co stary kod przepuszczał.
"""

import re

import pytest
from django.db import connection

# Tabele objęte soft-delete (django-soft-delete SoftDeleteModel) — jedyne
# źródło niezmiennika, świadomie utrzymywane jako lista, nie regex-owa
# heurystyka po nazwie.
#
# Faza 01 (2026-08-06): trzy tabele through autorstwa.
#
# Faza 02 MUSI DOPISAĆ TU 5 TABEL PUBLIKACJI:
#     "bpp_wydawnictwo_ciagle",
#     "bpp_wydawnictwo_zwarte",
#     "bpp_patent",
#     "bpp_praca_doktorska",
#     "bpp_praca_habilitacyjna",
# To WCIĄŻ jest jednolinijkowa (a ściślej: pięciolinijkowa) zmiana W TYM
# MIEJSCU — rdzeń kanarka (pg_depend) jest generyczny względem listy i nie
# wymaga żadnych innych zmian kodu. ALE: po dopisaniu tych 5 tabel kanarek
# realnie zaczerwieni się na WIĘCEJ niż na 3 znane winowajców z raportu —
# złapie też ``bpp_kronika_praca_doktorska_view`` i
# ``bpp_kronika_praca_habilitacyjna_view`` (czytają swoje tabele bez
# żadnego filtra i, w odróżnieniu od pozostałych trzech ``bpp_kronika_*``,
# NIE są jeszcze zweryfikowane jako martwe ani wpisane do ``WYJATKI`` —
# tego akurat nikt jeszcze nie sprawdzał, bo dotąd nie było powodu). To
# NIE jest fałszywy alarm do wyciszenia odruchowo — to dokładnie ta klasa
# odkrycia, dla której ten kanarek istnieje. Faza 02 ma:
#   a) albo zweryfikować, że są martwe (jak pozostałe trzy) i dopisać je
#      do ``WYJATKI`` z uzasadnieniem i datą,
#   b) albo je naprawić wzorcem z sekcji „Wzorzec naprawy" wyżej.
TABELE_SOFT_DELETE = [
    "bpp_wydawnictwo_ciagle_autor",
    "bpp_wydawnictwo_zwarte_autor",
    "bpp_patent_autor",
]

# Widoki-wyjątki: nazwa widoku -> uzasadnienie + data weryfikacji.
#
# Każdy wpis tutaj to ŚWIADOMA decyzja, nie cichy skip. Jeśli kanarek
# znajdzie NOWY widok bez filtra, którego nie ma na tej liście — to jest
# FAIL, a nie sygnał, żeby dopisać go tu po cichu. Zgłoś w recenzji/raporcie
# i zapytaj, zanim dopiszesz wyjątek.
#
# Zweryfikowane 2026-08-06 (naprawa-finalna-report.md, faza 01, punkt
# "Czego NIE zrobiłem" #1): trzy widoki ``bpp_kronika_*_view``
# (migracja ``0001_widoki_kronika.sql``) są MARTWE — zero konsumentów w
# kodzie produkcyjnym, szablonach i modelach Django. Jedyne trafienia
# "kronika" w repo poza katalogami migracji to `SOURCES.txt`
# (metadane pakietowania, nie kod). Naprawianie widoku, którego nikt nie
# czyta, byłoby czystym churnem — zostawione świadomie, do ewentualnego
# DROP-u przy innej okazji.
WYJATKI = {
    "bpp_kronika_wydawnictwo_ciagle_view": (
        "martwy widok (migracja 0001_widoki_kronika.sql) — zero "
        "konsumentów w kodzie/szablonach/modelach; jedyne trafienia "
        "'kronika' poza migracjami to SOURCES.txt. Zweryfikowane "
        "2026-08-06, naprawa-finalna-report.md faza 01."
    ),
    "bpp_kronika_wydawnictwo_zwarte_view": (
        "martwy widok (migracja 0001_widoki_kronika.sql) — zero "
        "konsumentów w kodzie/szablonach/modelach; jedyne trafienia "
        "'kronika' poza migracjami to SOURCES.txt. Zweryfikowane "
        "2026-08-06, naprawa-finalna-report.md faza 01."
    ),
    "bpp_kronika_patent_view": (
        "martwy widok (migracja 0001_widoki_kronika.sql) — zero "
        "konsumentów w kodzie/szablonach/modelach; jedyne trafienia "
        "'kronika' poza migracjami to SOURCES.txt. Zweryfikowane "
        "2026-08-06, naprawa-finalna-report.md faza 01."
    ),
}


def _regex_dla_tabeli(tabela):
    """Granica słowa po obu stronach — patrz docstring modułu, sekcja
    "Pułapka dopasowania"."""
    return re.compile(r"\b" + re.escape(tabela) + r"\b")


def widok_uzywa_tabeli(definicja, tabela):
    """Czy ``definicja`` widoku odwołuje się do ``tabela`` (jako całe słowo,
    nie substring cudzej, dłuższej nazwy).

    UWAGA: to jest matcher TEKSTOWY, zachowany wyłącznie dla własnych
    testów regresyjnych i dla symulacji starego (przed-naprawą) algorytmu
    w ``test_symulacja_fazy_02_...``. Rdzeń kanarka (``znajdz_winowajcow``)
    go NIE używa — patrz docstring modułu, sekcja "Źródło prawdy"."""
    return bool(_regex_dla_tabeli(tabela).search(definicja))


def _pobierz_widoki_publiczne(cur):
    """``(nazwa widoku, definicja)`` dla wszystkich widoków w schemacie
    ``public`` — ``pg_views.definition``, nie pliki migracji.

    Używane TYLKO przez testy sanity/mutacyjny/symulacyjny — nie przez
    rdzeń kanarka (patrz ``_widoki_czytajace_tabele`` /
    ``_widoki_zalezne_od_deleted_at`` niżej, oparte o ``pg_depend``)."""
    cur.execute("SELECT viewname, definition FROM pg_views WHERE schemaname = 'public'")
    return cur.fetchall()


def _widoki_czytajace_tabele(cur, tabele):
    """``{(widok, tabela)}`` dla par, gdzie ``widok`` FAKTYCZNIE zależy od
    ``tabela`` wg katalogu (``pg_depend``) — czyli „W czyta T", ustalone z
    tego samego źródła co zależność kolumnowa niżej, nie z tekstu.

    Zawiera zarówno zależności na poziomie kolumny (widok odwołuje się do
    konkretnej kolumny tabeli), jak i na poziomie całej relacji (widok
    używa tabeli w ``FROM``/``JOIN`` bez odwołania do żadnej jej kolumny —
    rzadkie, np. ``COUNT(*)``) — stąd brak filtra po ``refobjsubid``."""
    cur.execute(
        """
        SELECT DISTINCT v.relname, t.relname
        FROM pg_depend d
          JOIN pg_rewrite  r  ON r.oid = d.objid
          JOIN pg_class    v  ON v.oid = r.ev_class
          JOIN pg_namespace vn ON vn.oid = v.relnamespace
          JOIN pg_class    t  ON t.oid = d.refobjid
          JOIN pg_namespace tn ON tn.oid = t.relnamespace
        WHERE d.classid = 'pg_rewrite'::regclass
          AND d.refclassid = 'pg_class'::regclass
          AND vn.nspname = 'public'
          AND tn.nspname = 'public'
          AND t.relname = ANY(%s)
        """,
        [list(tabele)],
    )
    return set(cur.fetchall())


def _widoki_zalezne_od_deleted_at(cur, tabele):
    """``{(widok, tabela)}`` dla par, gdzie ``widok`` ma zależność
    KOLUMNOWĄ (``pg_depend`` → ``pg_attribute``) na ``tabela.deleted_at``.

    Dokładnie to samo narzędzie katalogowe, którego migracje
    ``0433``/``0489``/``0494`` używają do wyliczenia kolumn bramki ``WHEN``
    — patrz docstring modułu."""
    cur.execute(
        """
        SELECT DISTINCT v.relname, t.relname
        FROM pg_depend d
          JOIN pg_rewrite  r  ON r.oid = d.objid
          JOIN pg_class    v  ON v.oid = r.ev_class
          JOIN pg_namespace vn ON vn.oid = v.relnamespace
          JOIN pg_class    t  ON t.oid = d.refobjid
          JOIN pg_namespace tn ON tn.oid = t.relnamespace
          JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
        WHERE d.classid = 'pg_rewrite'::regclass
          AND d.refclassid = 'pg_class'::regclass
          AND vn.nspname = 'public'
          AND tn.nspname = 'public'
          AND t.relname = ANY(%s)
          AND a.attname = 'deleted_at'
          AND NOT a.attisdropped
        """,
        [list(tabele)],
    )
    return set(cur.fetchall())


def _winowajcy_bez_wyjatkow(cur, tabele):
    """Rdzeń bez filtrowania ``WYJATKI`` — pary (widok, tabela), gdzie widok
    czyta tabelę (``pg_depend``), ale nie zależy od jej ``deleted_at``
    (``pg_depend``). Wydzielone, żeby test dowodzący testowalność listy
    wyjątków (``test_kanarek_lapie_swiezy_wyjatek_...``) mógł zawołać
    dokładnie tę samą logikę bez powielania zapytań."""
    czytajace = _widoki_czytajace_tabele(cur, tabele)
    zalezne = _widoki_zalezne_od_deleted_at(cur, tabele)
    return czytajace - zalezne


def znajdz_winowajcow(cur, tabele=None, wyjatki=None):
    """Rdzeń kanarka: dla ``tabele`` (domyślnie ``TABELE_SOFT_DELETE``)
    zwraca listę ``(widok, tabela)``, gdzie widok czyta tabelę objętą
    soft-delete BEZ zależności od jej kolumny ``deleted_at`` (wg
    ``pg_depend``) i nie jest na liście ``wyjatki`` (domyślnie
    ``WYJATKI``).

    Przyjmuje kursor (nie listę widoków) — pyta katalog bezpośrednio, więc
    działa poprawnie także wewnątrz transakcji testowej PO mutacji widoku
    (``CREATE OR REPLACE VIEW`` w tej samej transakcji aktualizuje
    ``pg_depend`` od razu, katalogi Postgresa są transakcyjne)."""
    if tabele is None:
        tabele = TABELE_SOFT_DELETE
    if wyjatki is None:
        wyjatki = WYJATKI
    surowi = _winowajcy_bez_wyjatkow(cur, tabele)
    return sorted((widok, tabela) for widok, tabela in surowi if widok not in wyjatki)


def _komunikat_naprawy(winowajcy):
    linie = "\n".join(f"  - {widok} (czyta {tabela})" for widok, tabela in winowajcy)
    return (
        "Kanarek katalogowy: widoki poniżej czytają tabelę objętą "
        "soft-delete (wg pg_depend), ale NIE zależą od jej kolumny "
        "'deleted_at' (wg pg_depend) — soft-deletowane wiersze wyciekają "
        "do wyniku widoku.\n\n"
        f"{linie}\n\n"
        "NAPRAW jednym z wzorców (src/bpp/migration_util.py + przykłady):\n"
        "  - widok źródłowy / prosty WHERE-JOIN: widok_dopisz_warunek()\n"
        "    (patrz migracje 0489_soft_delete_autorzy_views.py,\n"
        "    0495_nowe_sumy_bez_skasowanych.py),\n"
        "  - widok z agregatem (count() itp.) po LEFT JOIN: użyj\n"
        "    'FILTER (WHERE ... deleted_at IS NULL)', NIE warunku w\n"
        "    WHERE/JOIN — inaczej LEFT JOIN staje się efektywnym INNER\n"
        "    JOIN i wywala z widoku cały wiersz nadrzędny, któremu\n"
        "    soft-deletowano WSZYSTKICH potomków (patrz\n"
        "    0494_liczba_autorow_bez_skasowanych.py).\n\n"
        "Jeśli widok jest MARTWY i naprawa byłaby czystym churnem — "
        "dopisz go do WYJATKI w tym pliku z uzasadnieniem i datą "
        "weryfikacji (sprawdź pg_depend / realnych konsumentów w "
        "kodzie/szablonach — NIE grep-iem po jednym słowie kluczowym), "
        "a NIE zgłaszaj tego po cichu."
    )


@pytest.mark.django_db
def test_kanarek_widoki_soft_delete_filtruja_po_deleted_at():
    """Rdzeń kanarka fazy 01/02+: widok czytający tabelę soft-delete musi
    zależeć (wg pg_depend) od jej kolumny ``deleted_at``, chyba że jest
    jawnie wyjątkiem."""
    with connection.cursor() as cur:
        winowajcy = znajdz_winowajcow(cur)
    assert not winowajcy, _komunikat_naprawy(winowajcy)


@pytest.mark.django_db
def test_kanarek_widzi_przynajmniej_widoki_zrodlowe():
    """Sanity kanarka: gdyby zapytanie do ``pg_views`` zwróciło pustą listę
    (zła nazwa kolumny, zły schemat, migracje niezastosowane), poprzedni
    test zazieleniłby się FAŁSZYWIE (``not []`` == ``True``). Pilnujemy, że
    kanarek realnie coś widzi."""
    with connection.cursor() as cur:
        widoki = _pobierz_widoki_publiczne(cur)
    nazwy = {w for w, _ in widoki}
    oczekiwane = {
        "bpp_wydawnictwo_ciagle_autorzy",
        "bpp_wydawnictwo_zwarte_autorzy",
        "bpp_patent_autorzy",
    }
    assert oczekiwane <= nazwy, (
        f"Oczekiwane widoki źródłowe nieznalezione w pg_views: "
        f"{oczekiwane - nazwy}. Kanarek patrzy na pustą/złą bazę."
    )


@pytest.mark.django_db
def test_kanarek_widzi_zaleznosci_pg_depend():
    """Sanity RDZENIA kanarka (pg_depend), analogiczne do testu wyżej dla
    pg_views: gdyby zapytania ``pg_depend`` zwracały pustą listę (zła
    nazwa kolumny/klasy w JOIN-ie, literówka w warunku), rdzeń zazieleniłby
    się FAŁSZYWIE — winowajcy byliby zawsze puści, bo obie strony różnicy
    ``czytajace - zalezne`` byłyby puste. Pilnujemy, że obie zależności
    katalogowe realnie coś widzą, na znanej, ustabilizowanej parze."""
    with connection.cursor() as cur:
        czytajace = _widoki_czytajace_tabele(cur, TABELE_SOFT_DELETE)
        zalezne = _widoki_zalezne_od_deleted_at(cur, TABELE_SOFT_DELETE)
    assert (
        "bpp_wydawnictwo_ciagle_autorzy",
        "bpp_wydawnictwo_ciagle_autor",
    ) in czytajace, "pg_depend nie widzi znanej relacji widok->tabela"
    assert (
        "bpp_wydawnictwo_ciagle_autorzy",
        "bpp_wydawnictwo_ciagle_autor",
    ) in zalezne, "pg_depend nie widzi znanej zależności widok->deleted_at"


@pytest.mark.django_db
def test_kanarek_lapie_swiezy_wyjatek_ktorego_nie_ma_na_liscie():
    """Kanarek NIE ma cichej furtki: widok bez filtra i BEZ wpisu w
    ``WYJATKI`` musi wywalić test, nawet jeśli akurat jest to jeden z
    już-znanych, zweryfikowanych martwych widoków ``kronika``."""
    with connection.cursor() as cur:
        # Celowo wołamy rdzeń BEZ filtrowania WYJATKI (_winowajcy_bez_wy-
        # jatkow) — symulujemy dokładnie sytuację "WYJATKI jest pusta/nie
        # wie o tym widoku", żeby sprawdzić, czy SAMA logika dopasowania
        # (bez listy wyjątków) łapie znane martwe widoki kronika.
        winowajcy = _winowajcy_bez_wyjatkow(cur, TABELE_SOFT_DELETE)
    zlapane = {w for w, _ in winowajcy}
    # Znane martwe widoki kronika MUSZĄ się tu pojawić — inaczej ta lista
    # wyjątków przestała być testowalna (np. ktoś je usunął z bazy albo
    # dopisał im filtr, więc WYJATKI trzeba by odchudzić).
    oczekiwane_bez_wyjatku = set(WYJATKI) & {
        "bpp_kronika_wydawnictwo_ciagle_view",
        "bpp_kronika_wydawnictwo_zwarte_view",
        "bpp_kronika_patent_view",
    }
    assert oczekiwane_bez_wyjatku <= zlapane, (
        "Kanarek przestał wykrywać znane widoki bez filtra po zdjęciu "
        "wyjątku — matcher/logika się zepsuły."
    )


# --- Testy SAMEGO matchera tekstowego (§ "Pułapka dopasowania") -------
#
# widok_uzywa_tabeli już nie jest częścią rdzenia kanarka (patrz docstring
# modułu), ale zostaje: 1) jako dokumentacja klasy błędu, przez którą rdzeń
# przesiadł się na pg_depend, 2) jako narzędzie symulacji starego
# algorytmu w teście dowodowym niżej.


@pytest.mark.parametrize(
    "tekst,oczekiwane",
    [
        ("SELECT * FROM bpp_wydawnictwo_ciagle_autor", True),
        ("SELECT * FROM bpp_wydawnictwo_ciagle_autor WHERE x", True),
        ('"bpp_wydawnictwo_ciagle_autor".autor_id', True),
        # Pułapka z brief-u: prefiks widoku źródłowego already-filtered.
        ("SELECT * FROM bpp_wydawnictwo_ciagle_autorzy", False),
        # Kolumna złożona z nazwy tabeli + "_id" — inny, dłuższy identyfikator.
        ("SELECT bpp_wydawnictwo_ciagle_autor_id FROM x", False),
        # Pusty/niepowiązany tekst.
        ("SELECT 1", False),
    ],
)
def test_matcher_nie_myli_autor_z_autorzy(tekst, oczekiwane):
    """``bpp_wydawnictwo_ciagle_autor`` jest PREFIKSEM
    ``bpp_wydawnictwo_ciagle_autorzy`` — dokładnie ta pułapka z briefu.
    Naiwny ``in``/``LIKE`` dałby ``True`` dla drugiego i czwartego
    przypadku. Ten test jest wyrocznią matchera — jeśli ktoś refaktorem
    zdejmie granicę słowa, ten test ma czerwienieć pierwszy."""
    assert widok_uzywa_tabeli(tekst, "bpp_wydawnictwo_ciagle_autor") is oczekiwane


@pytest.mark.parametrize(
    "tekst,oczekiwane",
    [
        # Odwrotna pułapka: "bpp_wydawnictwo_ciagle" jest PREFIKSEM
        # "bpp_wydawnictwo_ciagle_autor" — matcher szukający krótszej nazwy
        # (tabela publikacji) nie może się nabrać na dłuższą (tabela
        # autorstwa). Dokładnie ten mechanizm psuł stary (tekstowy)
        # algorytm w fazie 02 — patrz test symulacji niżej.
        ("SELECT * FROM bpp_wydawnictwo_ciagle", True),
        ("SELECT * FROM bpp_wydawnictwo_ciagle_autor", False),
        ("SELECT * FROM bpp_wydawnictwo_ciagle_view", False),
    ],
)
def test_matcher_prefiks_tabeli_publikacji_kontra_tabela_autorstwa(tekst, oczekiwane):
    """Ta sama klasa pułapki co ``test_matcher_nie_myli_autor_z_autorzy``,
    tylko w drugą stronę — istotna od momentu, gdy faza 02 dopisze
    ``bpp_wydawnictwo_ciagle`` (bez ``_autor``) do
    ``TABELE_SOFT_DELETE``."""
    assert widok_uzywa_tabeli(tekst, "bpp_wydawnictwo_ciagle") is oczekiwane


# --- Test dowodowy: symulacja fazy 02 -----------------------------------

# Pięć tabel publikacji, które faza 02 dopisze do TABELE_SOFT_DELETE.
# Zduplikowane tu ŚWIADOMIE (a nie zaimportowane) — ten test ma przetrwać
# NIEZMIENIONY moment, w którym faza 02 faktycznie dopisze je do stałej
# modułowej; do tego czasu musi budować symulację sam, niezależnie od
# TABELE_SOFT_DELETE.
_TABELE_PUBLIKACJI_FAZA_02 = [
    "bpp_wydawnictwo_ciagle",
    "bpp_wydawnictwo_zwarte",
    "bpp_patent",
    "bpp_praca_doktorska",
    "bpp_praca_habilitacyjna",
]


def _winowajcy_starym_algorytmem(widoki, tabele, wyjatki):
    """Odtworzenie DOKŁADNIE starego (przed naprawą 2026-08-06) rdzenia
    kanarka: substring ``"deleted_at" in definicja``, NIEKWALIFIKOWANY
    tabelą. Używane wyłącznie w teście dowodowym niżej — świadomie żywy
    kod błędu, nie refaktor do wspólnej funkcji, żeby test nie mógł
    przypadkiem zacząć wołać naprawionej wersji."""
    winowajcy = []
    for widok, definicja in widoki:
        if widok in wyjatki:
            continue
        for tabela in tabele:
            if not widok_uzywa_tabeli(definicja, tabela):
                continue
            if "deleted_at" not in definicja:
                winowajcy.append((widok, tabela))
    return winowajcy


@pytest.mark.django_db
def test_symulacja_fazy_02_kanarek_lapie_widoki_ktore_stara_wersja_przepuszczala():
    """DOWÓD, nie test dzisiejszego stanu bazy: symuluje przyszły stan po
    fazie 02 (soft-delete PUBLIKACJI), gdzie ``TABELE_SOFT_DELETE`` rośnie
    o 5 tabel publikacji, i udowadnia, że naprawiony (pg_depend) rdzeń
    kanarka łapie DOKŁADNIE to, co stary (tekstowy) rdzeń przepuszczał.

    ``TABELE_SOFT_DELETE`` w tym pliku NIE jest tu modyfikowane — budujemy
    lokalną, rozszerzoną listę i wołamy oba warianty algorytmu na tych
    samych, żywych danych z ``pg_views``/``pg_depend``. Ten test ma
    zostać na stałe (nie jest tymczasowym scratchem): to on dowodzi, że
    faza 02 dostanie od kanarka prawdziwą, kompletną listę winowajców
    jednym przebiegiem, zamiast — jak faza 01 — odkrywać ich pojedynczo
    przez awarie produkcyjne.

    Trzy konkretne pary (widok, tabela) niżej pochodzą z recenzji
    ``kanarek-fix-report.md`` (żywy katalog, 2026-08-06): widoki
    odziedziczyły tekstowo ``deleted_at`` z filtra po
    ``bpp_wydawnictwo_ciagle_autor`` (ten sam JOIN), mimo że nie filtrują
    wcale po WŁASNYM ``deleted_at`` tabeli ``bpp_wydawnictwo_ciagle``.
    """
    tabele_symulowane = TABELE_SOFT_DELETE + _TABELE_PUBLIKACJI_FAZA_02

    oczekiwane_falszywa_zielen = {
        ("bpp_wydawnictwo_ciagle_view", "bpp_wydawnictwo_ciagle"),
        ("bpp_nowe_sumy_wydawnictwo_ciagle_view", "bpp_wydawnictwo_ciagle"),
        (
            "rozbieznosci_dyscyplin_rozbieznoscizrodelview",
            "bpp_wydawnictwo_ciagle",
        ),
    }

    with connection.cursor() as cur:
        widoki = _pobierz_widoki_publiczne(cur)
        stary_winowajcy = set(
            _winowajcy_starym_algorytmem(widoki, tabele_symulowane, WYJATKI)
        )
        nowy_winowajcy = set(znajdz_winowajcow(cur, tabele=tabele_symulowane))

    # Dowód #1 (ISTNIENIE DZIURY): stary algorytm PRZEPUSZCZAŁ te 3 pary —
    # nie ma ich wśród jego winowajców, mimo że widoki naprawdę czytają
    # bpp_wydawnictwo_ciagle bez filtra po jej deleted_at. To jest
    # regression-proof samego buga opisanego w brief-ie/raporcie: jeśli
    # ten assert kiedyś zacznie padać, znaczy że któryś z tych widoków się
    # zmienił (np. ktoś usunął z jego tekstu literalne "deleted_at") i
    # test wymaga aktualizacji dowodu, nie że naprawa przestała działać.
    zlapane_przez_stary = stary_winowajcy & oczekiwane_falszywa_zielen
    assert not zlapane_przez_stary, (
        "Stary (tekstowy) algorytm złapał widoki, które wg raportu miał "
        f"PRZEPUSZCZAĆ (fałszywa zieleń): {zlapane_przez_stary}. Dane "
        "widoki się zmieniły — dowód wymaga aktualizacji, sprawdź "
        "kanarek-fix-report.md."
    )

    # Dowód #2 (NAPRAWA DZIAŁA): nowy (pg_depend) algorytm łapie wszystkie
    # 3 pary, których stary nie widział.
    niezlapane_przez_nowy = oczekiwane_falszywa_zielen - nowy_winowajcy
    assert not niezlapane_przez_nowy, (
        "Nowy (pg_depend) algorytm NIE złapał widoków z symulacji fazy "
        f"02, które miał złapać: {niezlapane_przez_nowy}. Naprawa nie "
        "działa albo się cofnęła."
    )


@pytest.mark.django_db
def test_mutacja_widoku_bez_filtra_kanarek_pada():
    """Weryfikacja MUTACYJNA: podmieniamy naprawiony widok źródłowy na
    wersję BEZ filtra (surowe ``CREATE OR REPLACE VIEW`` w transakcji
    testowej — Postgres DDL jest transakcyjny, więc to i tak by się cofnęło
    wraz z rollbackiem testu; mimo to przywracamy jawnie, żeby test
    dowodził całego cyklu, nie polegał tylko na tym, że pytest posprząta).

    Bez tego testu nie wiadomo, czy kanarek COKOLWIEK pilnuje — testy
    „substringowe" (czy widok zawiera ``deleted_at``) mogłyby przechodzić
    fałszywie pozytywnie z powodów niezwiązanych z logiką (np. literówka w
    nazwie kolumny w komentarzu SQL). Mutacja jest teraz jeszcze mocniejszym
    dowodem niż przy starym algorytmie: usuwa REALNĄ zależność kolumnową w
    ``pg_depend`` (nie tylko tekst), więc dowodzi, że rdzeń oparty o
    ``pg_depend`` faktycznie widzi zmianę w katalogu, a nie w tekście SQL-a.
    """
    widok = "bpp_wydawnictwo_ciagle_autorzy"
    with connection.cursor() as cur:
        cur.execute("SELECT pg_get_viewdef(%s::regclass)", [widok])
        oryginal = cur.fetchone()[0].rstrip().rstrip(";")

        # Format zgodny z pg_get_viewdef(regclass) BEZ jawnego pretty=true
        # (czyli tym samym, co zwraca pg_views.definition, którego używa
        # _pobierz_widoki_publiczne) — Postgres owija tu warunek w nawias.
        sufiks = "\n  WHERE (deleted_at IS NULL)"
        assert oryginal.endswith(sufiks), (
            f"{widok}: definicja nie kończy się oczekiwanym filtrem — "
            "test mutacyjny wymaga aktualizacji po zmianie SQL-a widoku. "
            f"Definicja: ...{oryginal[-120:]!r}"
        )
        zepsuta = oryginal[: -len(sufiks)]
        assert "deleted_at" not in zepsuta, (
            "zdjęcie sufiksu nie usunęło deleted_at z definicji — "
            "widok ma filtr gdzieś indziej niż w ostatnim WHERE"
        )

        try:
            cur.execute(f"CREATE OR REPLACE VIEW {widok} AS {zepsuta}")

            winowajcy = znajdz_winowajcow(cur)
            zlapani = {w for w, _ in winowajcy}
            assert widok in zlapani, (
                "MUTACJA NIE ZOSTAŁA WYKRYTA — kanarek nie pilnuje niczego. "
                f"Winowajcy po mutacji: {winowajcy}"
            )
        finally:
            # Przywracamy NIEZALEŻNIE od wyniku asercji powyżej — inaczej
            # test padający zostawiłby popsuty widok do końca transakcji
            # (nieszkodliwe przez rollback, ale przywracamy jawnie, patrz
            # docstring).
            cur.execute(f"CREATE OR REPLACE VIEW {widok} AS {oryginal}")

        winowajcy_po = znajdz_winowajcow(cur)
        zlapani_po = {w for w, _ in winowajcy_po}
        assert widok not in zlapani_po, (
            "widok nie wrócił do stanu naprawionego po przywróceniu "
            "oryginalnej definicji"
        )

"""Kanarek katalogowy: KAŻDY widok czytający tabelę objętą soft-delete
MUSI filtrować po ``deleted_at`` — albo być na jawnej, uzasadnionej liście
wyjątków.

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

## Źródło prawdy

``pg_views`` (schemat ``public``), na ŻYWEJ bazie — NIE pliki migracji.
Późniejsze migracje nadpisują wcześniejsze definicje widoków (
``CREATE OR REPLACE VIEW``), więc treść ``.sql`` w katalogu migracji nie
musi być tym, co faktycznie stoi w bazie. ``baseline-sql/baseline.sql`` też
zawodzi jako źródło — to snapshot sprzed części migracji (sprawdzone:
``baseline.sql`` ma ``NULL::bigint AS liczba_autorow`` zamiast realnego
``count()`` z migracji ``0494``).

## Pułapka dopasowania (naiwny ``in``/``LIKE``)

``bpp_wydawnictwo_ciagle_autor`` jest PREFIKSEM
``bpp_wydawnictwo_ciagle_autorzy`` (widok źródłowy already-filtered) — i,
symetrycznie w drugą stronę wobec fazy 02, ``bpp_wydawnictwo_ciagle``
(tabela publikacji) jest PREFIKSEM ``bpp_wydawnictwo_ciagle_autor``. Naiwne
dopasowanie substringiem dałoby fałszywe trafienia w obie strony. Matcher
niżej używa granicy słowa (``\\b``) na obu końcach nazwy tabeli — w Pythonie
``re`` podkreślnik ``_`` jest znakiem ``\\w``, więc ``\\b`` NIE tworzy
granicy między ``ciagle`` a następującym po nim ``_autor``, ani między
``autor`` a następującym po nim ``zy`` — obie „doklejki" są więc już z
konstrukcji odrzucane. ``test_matcher_...`` niżej to udowadnia i pilnuje,
żeby refaktor tego nie zepsuł.

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
# ⚠️ FAZA 02 MUSI DOPISAĆ TU 5 TABEL PUBLIKACJI — jednolinijkowa zmiana:
#     "bpp_wydawnictwo_ciagle",
#     "bpp_wydawnictwo_zwarte",
#     "bpp_patent",
#     "bpp_praca_doktorska",
#     "bpp_praca_habilitacyjna",
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
    nie substring cudzej, dłuższej nazwy)."""
    return bool(_regex_dla_tabeli(tabela).search(definicja))


def _pobierz_widoki_publiczne(cur):
    """``(nazwa widoku, definicja)`` dla wszystkich widoków w schemacie
    ``public`` — ``pg_views.definition``, nie pliki migracji."""
    cur.execute("SELECT viewname, definition FROM pg_views WHERE schemaname = 'public'")
    return cur.fetchall()


def znajdz_winowajcow(widoki):
    """Rdzeń kanarka: ``widoki`` to lista ``(nazwa, definicja)`` (jak z
    ``_pobierz_widoki_publiczne``). Zwraca listę ``(widok, tabela)`` dla
    par, gdzie widok czyta tabelę objętą soft-delete BEZ ``deleted_at`` w
    definicji i nie jest na liście ``WYJATKI``.

    Wydzielone z testu, żeby test mutacyjny mógł wywołać dokładnie tę samą
    logikę na spreparowanym stanie bazy, zamiast duplikować pętlę.
    """
    winowajcy = []
    for widok, definicja in widoki:
        if widok in WYJATKI:
            continue
        for tabela in TABELE_SOFT_DELETE:
            if not widok_uzywa_tabeli(definicja, tabela):
                continue
            if "deleted_at" not in definicja:
                winowajcy.append((widok, tabela))
    return winowajcy


def _komunikat_naprawy(winowajcy):
    linie = "\n".join(f"  - {widok} (czyta {tabela})" for widok, tabela in winowajcy)
    return (
        "Kanarek katalogowy: widoki poniżej czytają tabelę objętą "
        "soft-delete, ale ich definicja w pg_views NIE zawiera "
        "'deleted_at' — soft-deletowane wiersze wyciekają do wyniku "
        "widoku.\n\n"
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
        "weryfikacji (nie grep-iem po jednym słowie kluczowym — sprawdź "
        "pg_depend / realnych konsumentów), a NIE zgłaszaj tego po cichu."
    )


@pytest.mark.django_db
def test_kanarek_widoki_soft_delete_filtruja_po_deleted_at():
    """Rdzeń kanarka fazy 01/02+: widok czytający tabelę soft-delete musi
    znać ``deleted_at``, chyba że jest jawnie wyjątkiem."""
    with connection.cursor() as cur:
        widoki = _pobierz_widoki_publiczne(cur)
    winowajcy = znajdz_winowajcow(widoki)
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
def test_kanarek_lapie_swiezy_wyjatek_ktorego_nie_ma_na_liscie():
    """Kanarek NIE ma cichej furtki: widok bez filtra i BEZ wpisu w
    ``WYJATKI`` musi wywalić test, nawet jeśli akurat jest to jeden z
    już-znanych, zweryfikowanych martwych widoków ``kronika``."""
    with connection.cursor() as cur:
        widoki = _pobierz_widoki_publiczne(cur)
    # Celowo NIE wykluczamy widoków z WYJATKI tutaj (na odwrót niż
    # znajdz_winowajcow) — symulujemy dokładnie sytuację "WYJATKI jest
    # pusta/nie wie o tym widoku", żeby sprawdzić, czy SAMA logika
    # dopasowania (bez listy wyjątków) łapie znane martwe widoki kronika.
    winowajcy = [
        (widok, tabela)
        for widok, definicja in widoki
        for tabela in TABELE_SOFT_DELETE
        if widok_uzywa_tabeli(definicja, tabela) and "deleted_at" not in definicja
    ]
    # Znane martwe widoki kronika MUSZĄ się tu pojawić — inaczej ta lista
    # wyjątków przestała być testowalna (np. ktoś je usunął z bazy albo
    # dopisał im filtr, więc WYJATKI trzeba by odchudzić).
    zlapane = {w for w, _ in winowajcy}
    oczekiwane_bez_wyjatku = set(WYJATKI) & {
        "bpp_kronika_wydawnictwo_ciagle_view",
        "bpp_kronika_wydawnictwo_zwarte_view",
        "bpp_kronika_patent_view",
    }
    assert oczekiwane_bez_wyjatku <= zlapane, (
        "Kanarek przestał wykrywać znane widoki bez filtra po zdjęciu "
        "wyjątku — matcher/logika się zepsuły."
    )


# --- Testy SAMEGO matchera (§ "Pułapka dopasowania") ------------------


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
        # Odwrotna pułapka (aktualna od razu, na wyrost pod fazę 02):
        # "bpp_wydawnictwo_ciagle" jest PREFIKSEM
        # "bpp_wydawnictwo_ciagle_autor" — matcher szukający krótszej nazwy
        # (tabela publikacji) nie może się nabrać na dłuższą (tabela
        # autorstwa).
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
    nazwie kolumny w komentarzu SQL).
    """
    widok = "bpp_wydawnictwo_ciagle_autorzy"
    with connection.cursor() as cur:
        cur.execute("SELECT pg_get_viewdef(%s::regclass)", [widok])
        oryginal = cur.fetchone()[0].rstrip().rstrip(";")

        # Format zgodny z pg_get_viewdef(regclass) BEZ jawnego pretty=true
        # (czyli tym samym, co zwraca pg_views.definition, którego używa
        # znajdz_winowajcow) — Postgres owija tu warunek w nawias.
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

            widoki_po_mutacji = _pobierz_widoki_publiczne(cur)
            winowajcy = znajdz_winowajcow(widoki_po_mutacji)
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

        widoki_po_przywroceniu = _pobierz_widoki_publiczne(cur)
        winowajcy_po = znajdz_winowajcow(widoki_po_przywroceniu)
        zlapani_po = {w for w, _ in winowajcy_po}
        assert widok not in zlapani_po, (
            "widok nie wrócił do stanu naprawionego po przywróceniu "
            "oryginalnej definicji"
        )

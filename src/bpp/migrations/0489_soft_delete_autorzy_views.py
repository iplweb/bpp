"""Soft-delete autorstw: filtr w widokach + gałąź kasująca + bramka WHEN.

Kolejność operacji jest WYMUSZONA:

  1) widoki ``bpp_*_autorzy`` (dodają ``deleted_at`` do drzewa zapytania)  ->
  2) funkcje ``bpp_refresh_autor_*`` (gałąź kasująca)                      ->
  3) regeneracja bramki WHEN (czyta ``pg_depend`` PO definicji widoku z 1)

Kolumny bramki są wyliczane z ``pg_depend``, więc ``deleted_at`` wchodzi do niej
wyłącznie dlatego, że krok 1 wstawił tę kolumnę do definicji widoku.

Odwrócenie 1<->3 daje bramkę bez ``deleted_at``, czyli cichy staleness:
soft-deletowane autorstwo zostaje w ``bpp_autorzy_mat``.

Żadna z trzech zmian nie wystarcza sama:

- sam filtr widoku nie sprząta ``bpp_autorzy_mat`` — funkcja refresh po 0432
  robi wyłącznie ``INSERT ... ON CONFLICT DO UPDATE``, więc wypadnięcie wiersza
  ze źródła jest dla niej no-opem (patrz
  ``test_cache/test_soft_delete_preconditions.py``);
- bez ``deleted_at`` w bramce WHEN (0433) UPDATE soft-delete
  (``save(update_fields=['deleted_at', 'restored_at', 'transaction_id'])``)
  w ogóle nie dochodzi do funkcji triggera.

Definicje widoków i funkcji są GENEROWANE z introspekcji (tak jak w 0432/0433),
a nie przepisane do ``.sql`` — kopia rozjechałaby się przy najbliższej zmianie
kolumn. Stąd ``RunPython`` i ``importlib`` (nazwy modułów migracji zaczynają się
od cyfry, więc zwykły ``import`` nie przejdzie).
"""

import importlib
from pathlib import Path

from django.db import connection, migrations

_p0432 = importlib.import_module("bpp.migrations.0432_cache_trigger_plpgsql")
_p0433 = importlib.import_module("bpp.migrations.0433_cache_trigger_when_gate")

THROUGH_SITES = _p0432.THROUGH_SITES  # [(tabela through, model content_type), ...]

# Ostatnia migracja definiująca widoki bpp_*_autorzy. 0443 i 0458 też zawierają
# CREATE VIEW, ale dotyczą zupełnie innych widoków (bpp_kronika_*, bpp_nowe_sumy_*)
# — sprawdzone przy pisaniu tej migracji. Używane WYŁĄCZNIE w backward().
ZRODLO_ORYGINALNYCH_WIDOKOW = "0421_cache_trigger_pk_filter.sql"


def _widok(tabela):
    """``bpp_patent_autor`` -> ``bpp_patent_autorzy``."""
    return tabela[: -len("_autor")] + "_autorzy"


def _viewdef(cur, widok):
    cur.execute("SELECT pg_get_viewdef(%s::regclass, true)", [widok])
    return cur.fetchone()[0].rstrip().rstrip(";")


def _filtruj_widok(cur, tabela, widok):
    """Odcina z widoku ``*_autorzy`` wiersze soft-deletowanych autorstw.

    Dopisujemy ``WHERE`` do istniejącej, INTROSPEKOWANEJ definicji zamiast
    przepisywać ją ręcznie: definicja jest generowana (0421) i kopia
    rozjechałaby się przy następnej zmianie kolumn. ``CREATE OR REPLACE VIEW``
    zachowuje listę i typy kolumn, więc zależny ``bpp_autorzy`` (UNION po
    pięciu widokach) NIE jest kasowany — żadnego ``DROP ... CASCADE``.

    **Dlaczego filtr WEWNĘTRZNY, a nie owijka.** Plan zakładał owinięcie
    (``SELECT * FROM (<orig>) _orig WHERE NOT EXISTS (...)``) i kazał ZMIERZYĆ,
    czy owijka zachowuje plan wykonania. Zmierzone (PostgreSQL 16, EXPLAIN na
    bazie testowej):

    ===========================================  ==========  ==============
    zapytanie                                    oryginał    owijka
    ===========================================  ==========  ==============
    hot path triggera (``object_id_raw`` +       Index Scan  Nested Loop
    ``autor_id``)                                7.35        Anti Join 12.21
    pełny skan (przebudowa ``bpp_autorzy``)      11.50       26.84
    ===========================================  ==========  ==============

    Owijka NIE zachowuje planu (dokłada anti-join i sondę po pkey na każdy
    wiersz), więc — zgodnie z instrukcją planu na taki właśnie wypadek —
    dopisujemy ``deleted_at IS NULL`` do ``WHERE`` wewnętrznego. Ten wariant
    daje plan **identyczny** z oryginałem na hot-pathie (Index Scan, 7.35).

    ⚠️ Pomiar pełnego skanu z tabeli wyżej został zebrany na PUSTEJ bazie
    testowej i nie uogólnia się: pierwotnie zanotowano tam „2.36 — trafia w
    indeks na ``deleted_at``". Na produkcji tak NIE będzie. ``deleted_at IS
    NULL`` pasuje do ~100% wierszy, więc planner pod ten predykat wybierze
    seq scan, a nie indeks — i właśnie dlatego indeks z 0488 jest CZĘŚCIOWY
    (``WHERE deleted_at IS NOT NULL``, pod ``deleted_objects``). Filtr
    wewnętrzny wybieramy z powodu hot-pathu triggera, nie z powodu pełnego
    skanu.

    ⚠️ KLUCZ (pułapka, na której przejechał się pierwotny plan): w widokach
    ``*_autorzy`` kolumna ``object_id_raw`` to ``rekord_id``, czyli **id
    PUBLIKACJI**, a NIE pk wiersza through (ten siedzi w drugim elemencie
    kolumny-tablicy ``id``). Filtr po ``object_id_raw`` porównywałby id
    publikacji z id autorstwa: skasowane autorstwo zostawałoby w widoku, a przy
    zbieżności numerów wycinane byłyby autorstwa CUDZEJ publikacji. Filtr
    wewnętrzny nie porównuje ŻADNYCH kluczy — patrzy wprost na kolumnę wiersza,
    więc jest na tę pomyłkę odporny z konstrukcji. Regresji pilnuje
    ``test_widok_odcina_WLASCIWY_wiersz_a_nie_cudzy`` w
    ``src/bpp/tests/test_soft_delete/test_views_sql.py`` — testy substringowe
    (``deleted_at`` w ``pg_get_viewdef``) tego NIE łapią.
    """
    orig = _viewdef(cur, widok)
    if not orig.endswith(f"FROM {tabela}"):
        # Dopisanie WHERE jest poprawne tylko dla definicji kończącej się gołym
        # `FROM <tabela>`: bez aliasu (inaczej kwalifikacja kolumny nie
        # zadziała) i bez własnego WHERE (inaczej powstałby drugi WHERE).
        raise RuntimeError(
            f"{widok}: definicja nie konczy sie na 'FROM {tabela}' -- "
            f"dopisanie WHERE bylo by niepoprawne. Definicja: ...{orig[-120:]!r}"
        )
    cur.execute(
        f"CREATE OR REPLACE VIEW {widok} AS {orig} WHERE {tabela}.deleted_at IS NULL"
    )


def _funkcja_z_galezia_kasujaca(cur, tabela, model):
    """``bpp_refresh_autor_<model>()`` z 0432 + prolog kasujący.

    Ciało generowane identycznie jak ``_p0432._create_through_function`` (ten sam
    upsert z pozycyjnym mapowaniem kolumn), z jedną różnicą: gdy wiersz jest
    soft-deletowany, kasujemy go z ``bpp_autorzy_mat`` i wychodzimy. Klucz
    ``ARRAY[ct, NEW.id]`` jest ten sam co w ``_create_delete_through_function``
    (tam ``OLD.id``, tu ``NEW.id`` — przy UPDATE to ten sam wiersz).

    ``pg_advisory_xact_lock`` stoi PRZED rozgałęzieniem: kasowanie musi brać ten
    sam lock co upsert, inaczej wraca wyścig z #309.

    Restore (``deleted_at`` -> NULL) leci normalną ścieżką upsertu — wiersz
    wraca do widoku źródłowego, więc nic dodatkowego nie trzeba.
    """
    upsert = _p0432._upsert_sql(
        cur,
        "bpp_autorzy_mat",
        _widok(tabela),
        "object_id_raw = NEW.rekord_id AND autor_id = NEW.autor_id",
    )
    return f"""
CREATE OR REPLACE FUNCTION bpp_refresh_autor_{model}() RETURNS trigger
LANGUAGE plpgsql AS $bpp_body$
DECLARE ct integer;
BEGIN
      {_p0432._ct_lookup(model)}
      PERFORM pg_advisory_xact_lock(ct, NEW.rekord_id);
      IF NEW.deleted_at IS NOT NULL THEN
          DELETE FROM bpp_autorzy_mat WHERE id = ARRAY[ct, NEW.id]::integer[];
          RETURN NULL;
      END IF;
      {upsert};
      RETURN NULL;
END $bpp_body$;
"""


def _oryginalna_definicja_widoku(widok):
    """Instrukcja ``CREATE OR REPLACE VIEW <widok>`` sprzed tej migracji.

    ``pg_get_viewdef`` sprzed dopisania filtra nie jest w backward dostępny (w
    bazie stoi już definicja z ``WHERE deleted_at IS NULL``), więc bierzemy
    tekst z ostatniej migracji definiującej te widoki (patrz
    ``ZRODLO_ORYGINALNYCH_WIDOKOW``). ``str.index`` rzuca ``ValueError``, gdy
    markera nie ma — świadomie głośno, zamiast po cichu zostawić widok z filtrem.
    """
    sql = (Path(__file__).parent / ZRODLO_ORYGINALNYCH_WIDOKOW).read_text()
    poczatek = sql.index(f"CREATE OR REPLACE VIEW {widok} AS")
    # Instrukcja kończy się średnikiem na końcu linii FROM, po niej idzie linia
    # z samym ";" — pierwsze wystąpienie "\n;" po `poczatek` to właśnie ona.
    return sql[poczatek : sql.index("\n;", poczatek)]


def _regeneruj_bramke():
    """Ta sama logika co ``0433.forward``, ale tylko dla tabel through.

    Bramka jest wyliczana z ``pg_depend``, więc po zmianie definicji widoku
    (krok 1) sama wciągnie ``deleted_at``; po cofnięciu widoku (backward) sama
    ją zgubi. Tabele publikacji (``bpp_wydawnictwo_ciagle`` itd.) to faza 02 —
    tu ich nie ruszamy.
    """
    with connection.cursor() as cur:
        for tabela, refresh_fn, widoki in _p0433.GATED:
            if not tabela.endswith("_autor"):
                continue
            kolumny = _p0433._gate_columns(cur, tabela, widoki)
            if not kolumny:
                # Bezpiecznik z 0433: bez kolumn powstałby niebramkowany
                # UPDATE. Jeśli tu jesteśmy, krok 1 nie zadziałał.
                raise RuntimeError(
                    f"bramka dla {tabela}: pg_depend nie zwrocil zadnej kolumny "
                    f"(widoki={widoki}) -- nie tworze niezbramkowanego UPDATE"
                )
            when = _p0433._when_clause(kolumny)
            cur.execute(f"DROP TRIGGER IF EXISTS {tabela}_cache_upd ON {tabela};")
            cur.execute(
                f"CREATE TRIGGER {tabela}_cache_upd AFTER UPDATE ON {tabela} "
                f"FOR EACH ROW WHEN ({when}) "
                f"EXECUTE PROCEDURE {refresh_fn}();"
            )


def forward(apps, schema_editor):
    with connection.cursor() as cur:
        for tabela, _model in THROUGH_SITES:  # 1) widoki
            _filtruj_widok(cur, tabela, _widok(tabela))
        for tabela, model in THROUGH_SITES:  # 2) funkcje
            cur.execute(_funkcja_z_galezia_kasujaca(cur, tabela, model))
    _regeneruj_bramke()  # 3) bramka


def backward(apps, schema_editor):
    with connection.cursor() as cur:
        for tabela, _model in THROUGH_SITES:  # 1) widoki bez filtra
            cur.execute(_oryginalna_definicja_widoku(_widok(tabela)))
        for tabela, model in THROUGH_SITES:  # 2) funkcje bez gałęzi kasującej
            cur.execute(_p0432._create_through_function(cur, tabela, model))
    _regeneruj_bramke()  # 3) bramka (deleted_at zniknie z pg_depend samo)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0488_autor_soft_delete_fields"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]

"""Testy optymalizacji triggera cache (issue #311): widoki per-typ wystawiają
surową kolumnę object_id_raw, a bpp_refresh_cache() filtruje po niej (index seek)
zamiast po wyliczanej kolumnie-tablicy na unii. Zachowanie cache musi pozostać
identyczne — to jest siatka bezpieczeństwa dla tej zmiany.
"""

import pytest
from django.db import connection
from model_bakery import baker

from bpp.models import Autor, Jednostka, Rekord, Wydawnictwo_Ciagle

VIEWS_Z_OBJECT_ID_RAW = [
    "bpp_wydawnictwo_ciagle_view",
    "bpp_wydawnictwo_zwarte_view",
    "bpp_patent_view",
    "bpp_praca_doktorska_view",
    "bpp_praca_habilitacyjna_view",
    "bpp_wydawnictwo_ciagle_autorzy",
    "bpp_wydawnictwo_zwarte_autorzy",
    "bpp_patent_autorzy",
    "bpp_praca_doktorska_autorzy",
    "bpp_praca_habilitacyjna_autorzy",
]


@pytest.mark.django_db
def test_object_id_raw_obecne_na_wszystkich_widokach():
    with connection.cursor() as c:
        for v in VIEWS_Z_OBJECT_ID_RAW:
            c.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = %s AND column_name = 'object_id_raw'",
                [v],
            )
            assert c.fetchone() is not None, f"{v} nie ma kolumny object_id_raw"


def _zasiej_klonujac(cursor, table, n):
    """Szybko rozdmuchuje `table` do `n`+ wierszy, klonując istniejący wiersz
    jednym ``INSERT ... SELECT × generate_series`` (bez kosztu baker
    per-wiersz — ~0.3 s zamiast ~17 s dla 600 wierszy).

    Kolumny UNIQUE (poza PK) nullujemy, żeby nie złamać ograniczeń przy
    duplikowaniu wiersza. PK (``id``) pomijamy — generuje się z sekwencji.
    """
    cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s ORDER BY ordinal_position",
        [table],
    )
    cols = [r[0] for r in cursor.fetchall()]
    cursor.execute(
        "SELECT a.attname FROM pg_index i "
        "JOIN pg_attribute a ON a.attrelid = i.indrelid "
        "  AND a.attnum = ANY(i.indkey) "
        "WHERE i.indrelid = %s::regclass "
        "  AND i.indisunique AND NOT i.indisprimary",
        [table],
    )
    unique_cols = {r[0] for r in cursor.fetchall()}

    insert_cols = [col for col in cols if col != "id"]
    select_exprs = ["NULL" if col in unique_cols else col for col in insert_cols]
    collist = ", ".join(insert_cols)
    selectlist = ", ".join(select_exprs)
    cursor.execute(
        f"INSERT INTO {table} ({collist}) "  # noqa: S608 — nazwy z katalogu, nie userinput
        f"SELECT {selectlist} FROM {table}, generate_series(1, %s)",
        [n],
    )


@pytest.mark.django_db
def test_object_id_raw_daje_index_seek_na_pk():
    """Filtr po object_id_raw musi schodzić do Index Cond na PK tabeli bazowej,
    nie do Seq Scan — sedno optymalizacji (#311).

    Sprawdzamy, że na realnym (dużym) zbiorze planner SAM wybiera index scan
    po PK. Testowa tabela jest pusta, więc najpierw zasiewamy ją do rozmiaru,
    przy którym Seq Scan jest droższy od Index Scan (~600 wierszy → ~120
    stron), i robimy ANALYZE, żeby planner widział realne statystyki.

    Bez tego zasiewu test jest *order-dependent* i flakuje w pełnej suite:

    - W IZOLACJI tabela jest świeża i nigdy nie ANALYZE-owana
      (``pg_class.relpages = 0``, ``reltuples = -1``). Planner heurystyką
      ``estimate_rel_size`` zakłada wtedy ~10 stron, więc Index Scan i tak
      wygrywa kosztowo → test „przechodzi" przypadkiem.
    - W PEŁNEJ SUITE insert/rollback churn z setek testów przekracza próg
      autoanalyze (``50 + 0.1·reltuples``); autovacuum w tle ustawia realne
      ``relpages = 1`` → planner poprawnie wybiera Seq Scan na 1-stronicowej
      tabeli → test pada.

    Czyli pierwotnie test sprawdzał *rozmiar* tabeli (zależny od statystyk),
    a nie samą optymalizację. Po zasianiu sprawdza to, o co chodzi: że
    predykat po ``object_id_raw`` schodzi do indeksowanego PK tabeli bazowej
    i że na realnym wolumenie planner go używa zamiast Seq Scanu. Regres, w
    którym ``object_id_raw`` przestałby schodzić do PK (np. stałby się
    wyliczaną kolumną na unii), wywali ten test, bo planner nie miałby jak
    użyć indeksu PK.
    """
    wc = baker.make(Wydawnictwo_Ciagle)
    with connection.cursor() as c:
        _zasiej_klonujac(c, "bpp_wydawnictwo_ciagle", 600)
        c.execute("ANALYZE bpp_wydawnictwo_ciagle")
        c.execute(
            "EXPLAIN SELECT * FROM bpp_wydawnictwo_ciagle_view "
            "WHERE object_id_raw = %s",
            [wc.pk],
        )
        plan = "\n".join(row[0] for row in c.fetchall())
    assert "bpp_wydawnictwo_ciagle_pkey" in plan, plan
    assert f"Index Cond: (id = {wc.pk})" in plan, plan
    assert "Seq Scan on bpp_wydawnictwo_ciagle " not in plan, plan


@pytest.mark.django_db
def test_edycja_publikacji_odswieza_rekord_mat(standard_data, denorms):
    wc = baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="STARY TYTUL", szczegoly="sz", uwagi="u"
    )
    assert Rekord.objects.get_for_model(wc).tytul_oryginalny == "STARY TYTUL"
    wc.tytul_oryginalny = "NOWY TYTUL"
    wc.save()
    assert Rekord.objects.get_for_model(wc).tytul_oryginalny == "NOWY TYTUL"


@pytest.mark.django_db
def test_dodanie_i_usuniecie_autora_odswieza_autorzy_mat(standard_data, denorms):
    wc = baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="Test", szczegoly="sz", uwagi="u"
    )
    a = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    j = baker.make(Jednostka)
    wca = wc.dodaj_autora(a, j)
    denorms.flush()
    assert Rekord.objects.get_for_model(wc).autorzy_set.filter(autor=a).exists()

    # edycja/usunięcie jednego wiersza *_autor (ścieżka through-table z autor_id)
    wca.delete()
    denorms.flush()
    assert not Rekord.objects.get_for_model(wc).autorzy_set.filter(autor=a).exists()

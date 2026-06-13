"""Kanarki portu bpp_refresh_cache PL/Python -> PL/pgSQL + bramki WHEN.

Spec: docs/deweloper/spec-bpp-refresh-cache-plpgsql-2026-06.md

Trzy klasy testow:

1. ``test_cache_functions_are_plpgsql`` -- po porcie (migracja 0432) funkcje
   triggera musza byc statycznym PL/pgSQL, nie dynamicznym PL/Python.
   RED dopoki port nie istnieje.

2. ``test_view_feeding_column_keeps_mat_fresh`` / ``..._autorzy_mat_fresh``
   -- KANAREK STALENESS (spec sec. 3, obowiazkowy). Dla kolumny bazowej
   zasilajacej widok: surowy UPDATE -> ``mat`` musi byc == swiezo policzony
   widok. Brak kolumny w bramce WHEN = cichy staleness = ten test na czerwono.
   Pokrywa pulapke przemianowania (``wydawca_opis`` -> ``wydawnictwo`` w
   zwarte) i kolumne through-table.

3. ``test_gate_skips_non_view_column`` -- bramka WHEN (migracja 0433) pomija
   jalowe odswiezenie: surowy UPDATE kolumny SPOZA widoku
   (``weryfikacja_punktacji``) NIE przepisuje wiersza ``bpp_rekord_mat``
   (ctid bez zmian). RED dopoki trigger jest bezwarunkowy.

Wszystkie testy uzywaja SUROWEGO SQL-a, by izolowac sam trigger bazodanowy
(bez denorm / sygnalow Django).
"""

import pytest
from django.db import connection
from model_bakery import baker

from bpp.models import Autor, Jednostka, Wydawnictwo_Ciagle
from bpp.tests.util import any_ciagle, any_zwarte


def _cols(cur, relname):
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
        [relname],
    )
    return [r[0] for r in cur.fetchall()]


def _ct(cur, model):
    cur.execute(
        "SELECT id FROM django_content_type WHERE app_label='bpp' AND model=%s",
        [model],
    )
    return cur.fetchone()[0]


def _q(c):
    return '"' + c + '"'


def _rekord_mat_row(cur, ct, pk):
    cols = _cols(cur, "bpp_rekord_mat")
    cur.execute(
        f"SELECT {', '.join(_q(c) for c in cols)} FROM bpp_rekord_mat "
        f"WHERE id = ARRAY[%s, %s]::integer[]",
        [ct, pk],
    )
    return cur.fetchone()


def _rekord_view_row(cur, view, pk):
    src = [c for c in _cols(cur, view) if c != "object_id_raw"]
    cur.execute(
        f"SELECT {', '.join(_q(c) for c in src)} FROM {view} WHERE object_id_raw = %s",
        [pk],
    )
    return cur.fetchone()


def _autorzy_mat_row(cur, ct, through_pk):
    cols = _cols(cur, "bpp_autorzy_mat")
    cur.execute(
        f"SELECT {', '.join(_q(c) for c in cols)} FROM bpp_autorzy_mat "
        f"WHERE id = ARRAY[%s, %s]::integer[]",
        [ct, through_pk],
    )
    return cur.fetchone()


def _autorzy_view_row(cur, view, object_id_raw, autor_id):
    src = [c for c in _cols(cur, view) if c != "object_id_raw"]
    cur.execute(
        f"SELECT {', '.join(_q(c) for c in src)} FROM {view} "
        f"WHERE object_id_raw = %s AND autor_id = %s",
        [object_id_raw, autor_id],
    )
    return cur.fetchone()


# ---------------------------------------------------------------------------
# 1. Port: funkcje sa PL/pgSQL
# ---------------------------------------------------------------------------

EXPECTED_FUNCTIONS = [
    "bpp_refresh_rekord_wydawnictwo_ciagle",
    "bpp_refresh_rekord_wydawnictwo_zwarte",
    "bpp_refresh_rekord_patent",
    "bpp_refresh_rekord_praca_doktorska",
    "bpp_refresh_rekord_praca_habilitacyjna",
    "bpp_refresh_autor_wydawnictwo_ciagle",
    "bpp_refresh_autor_wydawnictwo_zwarte",
    "bpp_refresh_autor_patent",
    "bpp_delete_rekord_wydawnictwo_ciagle",
    "bpp_delete_rekord_wydawnictwo_zwarte",
    "bpp_delete_rekord_patent",
    "bpp_delete_rekord_praca_doktorska",
    "bpp_delete_rekord_praca_habilitacyjna",
    "bpp_delete_autor_wydawnictwo_ciagle",
    "bpp_delete_autor_wydawnictwo_zwarte",
    "bpp_delete_autor_patent",
]


@pytest.mark.django_db
@pytest.mark.parametrize("fn", EXPECTED_FUNCTIONS)
def test_cache_functions_are_plpgsql(fn):
    with connection.cursor() as cur:
        cur.execute(
            "SELECT l.lanname FROM pg_proc p JOIN pg_language l ON l.oid=p.prolang "
            "WHERE p.proname=%s",
            [fn],
        )
        row = cur.fetchone()
    assert row is not None, f"funkcja {fn} nie istnieje (port nie zrobiony)"
    assert row[0] == "plpgsql", f"{fn} jest w jezyku {row[0]}, oczekiwano plpgsql"


# ---------------------------------------------------------------------------
# 2. Kanarek staleness: mat == widok dla kazdej zasilajacej kolumny
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model,table,view,column,perturb",
    [
        # ciagle: kolumny tekstowe, nazwa = nazwa kolumny mat
        (
            "wydawnictwo_ciagle",
            "bpp_wydawnictwo_ciagle",
            "bpp_wydawnictwo_ciagle_view",
            "tytul_oryginalny",
            "COALESCE(tytul_oryginalny, '') || 'KANAREK'",
        ),
        (
            "wydawnictwo_ciagle",
            "bpp_wydawnictwo_ciagle",
            "bpp_wydawnictwo_ciagle_view",
            "uwagi",
            "COALESCE(uwagi, '') || 'KANAREK'",
        ),
        # zwarte: PULAPKA PRZEMIANOWANIA -- wydawca_opis zasila widokowa
        # kolumne 'wydawnictwo'. Dopasowanie po nazwie zgubiloby ja.
        (
            "wydawnictwo_zwarte",
            "bpp_wydawnictwo_zwarte",
            "bpp_wydawnictwo_zwarte_view",
            "wydawca_opis",
            "COALESCE(wydawca_opis, '') || 'KANAREK'",
        ),
    ],
)
def test_view_feeding_column_keeps_mat_fresh(model, table, view, column, perturb):
    if table == "bpp_wydawnictwo_ciagle":
        rec = any_ciagle(tytul_oryginalny="Kanarkowa", uwagi="u")
    else:
        rec = any_zwarte(tytul_oryginalny="Kanarkowa", uwagi="u")
    pk = rec.pk

    with connection.cursor() as cur:
        ct = _ct(cur, model)
        cur.execute(f"UPDATE {table} SET {column} = {perturb} WHERE id = %s", [pk])

        mat = _rekord_mat_row(cur, ct, pk)
        widok = _rekord_view_row(cur, view, pk)

    assert mat == widok, (
        f"po zmianie {table}.{column} wiersz bpp_rekord_mat != widok "
        f"(kolumna zgubiona w bramce? cichy staleness)"
    )


@pytest.mark.django_db
def test_through_feeding_column_keeps_autorzy_mat_fresh(standard_data, denorms):
    wc = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Kanarek through",
        szczegoly="sz",
        uwagi="u",
    )
    j = baker.make(Jednostka)
    a = baker.make(Autor, imiona="Jan", nazwisko="Kanarek")
    wca = wc.dodaj_autora(a, j, zapisany_jako="Jan Kanarek")
    denorms.flush()

    with connection.cursor() as cur:
        ct = _ct(cur, "wydawnictwo_ciagle")
        cur.execute(
            "UPDATE bpp_wydawnictwo_ciagle_autor "
            "SET zapisany_jako = zapisany_jako || 'KANAREK' WHERE id = %s",
            [wca.pk],
        )
        mat = _autorzy_mat_row(cur, ct, wca.pk)
        widok = _autorzy_view_row(cur, "bpp_wydawnictwo_ciagle_autorzy", wc.pk, a.pk)

    assert mat == widok, (
        "po zmianie bpp_wydawnictwo_ciagle_autor.zapisany_jako "
        "wiersz bpp_autorzy_mat != widok (cichy staleness)"
    )


# ---------------------------------------------------------------------------
# 3. Bramka WHEN: skip jalowego odswiezenia na kolumnie spoza widoku
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_gate_skips_non_view_column():
    """weryfikacja_punktacji nie zasila zadnego widoku -> bramka WHEN ma
    pominac UPDATE: bpp_rekord_mat NIE przepisany (ctid bez zmian).

    ctid (fizyczne polozenie krotki), nie xmin: w obrebie jednej transakcji
    testowej kazdy zapis ma to samo xid, wiec xmin sie nie rusza nawet przy
    przepisaniu; ctid zmienia sie na KAZDYM UPDATE krotki.

    RED dopoki trigger UPDATE jest bezwarunkowy (przepisuje zawsze)."""
    wc = any_ciagle(tytul_oryginalny="Bramka")
    pk = wc.pk

    with connection.cursor() as cur:
        ct = _ct(cur, "wydawnictwo_ciagle")

        def ctid():
            cur.execute(
                "SELECT ctid::text FROM bpp_rekord_mat "
                "WHERE id = ARRAY[%s, %s]::integer[]",
                [ct, pk],
            )
            return cur.fetchone()[0]

        przed = ctid()
        cur.execute(
            "UPDATE bpp_wydawnictwo_ciagle "
            "SET weryfikacja_punktacji = NOT COALESCE(weryfikacja_punktacji, false) "
            "WHERE id = %s",
            [pk],
        )
        po = ctid()

    assert po == przed, (
        "UPDATE kolumny spoza widoku (weryfikacja_punktacji) przepisal "
        f"bpp_rekord_mat (ctid {przed} -> {po}) -- bramka WHEN nie dziala"
    )

"""Warunki wstepne soft-delete wobec triggerow cache (PR #312, faza 01).

Spec soft-delete (2026-06-04) zaklada dwa fakty o warstwie cache:

1. ``deleted_at`` ustawione UPDATE-em dolecialoby do triggera cache;
2. filtr ``deleted_at IS NULL`` w widoku zrodlowym WYSTARCZY, bo trigger na
   UPDATE robi bezwarunkowy DELETE z ``_mat`` przed upsertem ("inwariant,
   ktory MUSI przetrwac optymalizacje" -- plan 00).

Oba fakty przestaly obowiazywac po migracjach 0432 (port PL/pgSQL, upsert bez
DELETE) i 0433 (bramka WHEN na liscie kolumn z pg_depend). Te testy to
przypinaja: sa ZIELONE na obecnym kodzie, czyli dokumentuja stan "soft-delete
by nie zadzialal". Faza 01 ma je odwrocic (zmienic asercje na docelowe) razem
z wprowadzeniem gałęzi kasujacej w funkcjach refresh + regeneracja bramki.

Surowy SQL, zeby izolowac sam trigger bazodanowy (bez denorm / sygnalow
Django). Kolumne ``deleted_at`` dokladamy ALTER-em wewnatrz transakcji
testowej -- DDL w Postgresie jest transakcyjny, wiec rollback ja sprzata.
"""

import pytest
from django.db import connection

from bpp.tests.util import any_ciagle


def _ct(cur, model):
    cur.execute(
        "SELECT id FROM django_content_type WHERE app_label='bpp' AND model=%s",
        [model],
    )
    return cur.fetchone()[0]


def _ctid(cur, ct, pk):
    """Fizyczne polozenie krotki w bpp_rekord_mat; None gdy wiersza nie ma.

    ctid, nie xmin: w obrebie jednej transakcji testowej kazdy zapis ma to samo
    xid, wiec xmin sie nie rusza nawet przy przepisaniu wiersza.
    """
    cur.execute(
        "SELECT ctid::text FROM bpp_rekord_mat WHERE id = ARRAY[%s, %s]::integer[]",
        [ct, pk],
    )
    row = cur.fetchone()
    return row[0] if row else None


def _dodaj_deleted_at(cur):
    cur.execute("ALTER TABLE bpp_wydawnictwo_ciagle ADD COLUMN deleted_at timestamptz")


def _filtruj_widok_po_deleted_at(cur):
    """Owija bpp_wydawnictwo_ciagle_view filtrem deleted_at IS NULL.

    Odpowiednik "mechanizmu #1" ze specu, bez ruszania oryginalnej definicji
    (CREATE OR REPLACE zachowuje liste kolumn -- bpp_rekord, ktory ten widok
    UNION-uje, pozostaje wazny).
    """
    cur.execute("SELECT pg_get_viewdef('bpp_wydawnictwo_ciagle_view'::regclass, true)")
    orig = cur.fetchone()[0].rstrip().rstrip(";")
    cur.execute(
        f"CREATE OR REPLACE VIEW bpp_wydawnictwo_ciagle_view AS "
        f"SELECT * FROM ({orig}) _orig "
        f"WHERE _orig.object_id_raw NOT IN ("
        f"    SELECT id FROM bpp_wydawnictwo_ciagle WHERE deleted_at IS NOT NULL)"
    )


@pytest.mark.django_db
def test_update_samego_deleted_at_nie_odpala_triggera():
    """Bramka WHEN (0433) nie zna deleted_at -> UPDATE soft-delete nie wchodzi.

    django-soft-delete kasuje przez
    ``save(update_fields=['deleted_at', 'restored_at', 'transaction_id'])``,
    wiec UPDATE dotyka WYLACZNIE kolumn spoza bramki. Zaden atrybut zasilajacy
    widok sie nie zmienia -> trigger sie nie odpala -> wiersz zostaje w
    bpp_rekord_mat (ctid bez zmian).
    """
    # DDL PRZED utworzeniem rekordu: ALTER TABLE nie przejdzie, gdy tabela ma
    # zakolejkowane zdarzenia wyzwalaczy z INSERT-a w tej samej transakcji.
    with connection.cursor() as cur:
        _dodaj_deleted_at(cur)

    wc = any_ciagle(tytul_oryginalny="Bramka a soft-delete")
    pk = wc.pk

    with connection.cursor() as cur:
        ct = _ct(cur, "wydawnictwo_ciagle")

        przed = _ctid(cur, ct, pk)
        assert przed is not None, "wiersz powinien byc w bpp_rekord_mat po INSERT"

        cur.execute(
            "UPDATE bpp_wydawnictwo_ciagle SET deleted_at = now() WHERE id = %s",
            [pk],
        )
        po = _ctid(cur, ct, pk)

    assert po == przed, (
        "UPDATE samego deleted_at przepisal bpp_rekord_mat "
        f"(ctid {przed} -> {po}) -- bramka WHEN najwyrazniej zna deleted_at"
    )


@pytest.mark.django_db
def test_filtr_widoku_sam_nie_usuwa_wiersza_z_mat():
    """Upsert bez DELETE (0432): odfiltrowanie z widoku NIE czysci _mat.

    Nawet gdy trigger SIE ODPALI (wymuszamy to UPDATE-em bramkowanej kolumny
    ``rok``), funkcja refresh robi tylko
    ``INSERT ... SELECT FROM widok ... ON CONFLICT DO UPDATE``. Widok nie
    zwraca wiersza -> INSERT wybiera zero wierszy -> no-op -> stary wiersz
    przezywa w bpp_rekord_mat.

    To obala "inwariant delete-first" z planu 00, na ktorym opiera sie
    wystarczalnosc mechanizmu #1.
    """
    # Cale DDL przed INSERT-em (patrz test wyzej). Filtr widoku jest juz
    # aktywny przy tworzeniu rekordu, ale deleted_at jest wtedy NULL, wiec
    # wiersz normalnie wchodzi do bpp_rekord_mat.
    with connection.cursor() as cur:
        _dodaj_deleted_at(cur)
        _filtruj_widok_po_deleted_at(cur)

    wc = any_ciagle(tytul_oryginalny="Filtr widoku bez DELETE", rok=2020)
    pk = wc.pk

    with connection.cursor() as cur:
        ct = _ct(cur, "wydawnictwo_ciagle")

        assert _ctid(cur, ct, pk) is not None

        # soft-delete: wiersz wypada z widoku zrodlowego
        cur.execute(
            "UPDATE bpp_wydawnictwo_ciagle SET deleted_at = now() WHERE id = %s",
            [pk],
        )
        # ... i wymuszamy odpalenie triggera zmiana kolumny Z bramki
        cur.execute("UPDATE bpp_wydawnictwo_ciagle SET rok = 2021 WHERE id = %s", [pk])

        cur.execute(
            "SELECT count(*) FROM bpp_wydawnictwo_ciagle_view WHERE object_id_raw = %s",
            [pk],
        )
        w_widoku = cur.fetchone()[0]
        po = _ctid(cur, ct, pk)

    assert w_widoku == 0, "widok zrodlowy powinien juz nie zwracac wiersza"
    assert po is not None, (
        "wiersz zniknal z bpp_rekord_mat -- funkcja refresh jednak kasuje "
        "przed upsertem (inwariant delete-first zyje)"
    )

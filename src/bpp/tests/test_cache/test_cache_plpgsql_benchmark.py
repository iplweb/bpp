"""Benchmark VC (PL/pgSQL) vs V0 (PL/Python) + dowod semantycznej neutralnosci.

Spec: docs/deweloper/spec-bpp-refresh-cache-plpgsql-2026-06.md (sek. 1, Zalacznik A).

Dwa twierdzenia:

1. SEMANTYKA (twardy gejt): ``bpp_rekord_mat`` policzony przez port PL/pgSQL jest
   BAJTOWO identyczny z policzonym przez stara funkcje PL/Python (agregat md5 po
   calej tabeli). To jest wlasciwy dowod poprawnosci portu.

2. WYDAJNOSC (informacyjnie + sanity): serwerowy czas bulk-UPDATE (min z prob,
   1 warm-up odrzucony) -- port ma byc szybszy od PL/Python (spec: ~2,2-2,3x na
   czystych komorkach). Na malym zbiorze w CI margines jest skromniejszy, wiec
   asercja jest konserwatywna (port nie wolniejszy), a liczby ida do stdout.

Mechanika: zbior testowy jest staly; mierzymy ten sam bulk-UPDATE raz na porcie
(stan biezacy), raz po przelaczeniu na funkcje V0 (plpython3u + zlaczone
triggery, odtworzone z 0429/0400 bez BEGIN/COMMIT). DDL jest transakcyjne, wiec
przelaczenie zyje tylko w transakcji testu.
"""

from pathlib import Path

import pytest
from django.db import connection
from model_bakery import baker

from bpp.models import Autor, Jednostka, Wydawnictwo_Ciagle

N = 120
REPS = 5  # 1 warm-up odrzucony, min z reszty

_MIGR = Path(__file__).resolve().parents[3] / "bpp" / "migrations"

BENCH_FN = """
CREATE OR REPLACE FUNCTION bench_update(setclause text, n int)
RETURNS TABLE(ms numeric, mat_writes bigint) LANGUAGE plpgsql AS $$
DECLARE t0 timestamptz;
BEGIN
  t0 := clock_timestamp();
  EXECUTE format('UPDATE bpp_wydawnictwo_ciagle SET %s WHERE id IN '
    '(SELECT id FROM bpp_wydawnictwo_ciagle ORDER BY id LIMIT %s)', setclause, n);
  ms := round(extract(epoch from clock_timestamp()-t0)*1000,1);
  SELECT COALESCE(sum(n_tup_ins+n_tup_upd),0) INTO mat_writes
    FROM pg_stat_xact_user_tables WHERE relname='bpp_rekord_mat';
  RETURN NEXT;
END $$;
"""


def _strip_tx(sql):
    # 0429 owija sie w BEGIN; ... COMMIT; -- w transakcji testu COMMIT zerwalby
    # izolacje (rollback). Wytnij sterowanie transakcja, zostaw DDL.
    lines = []
    for line in sql.splitlines():
        if line.strip().upper() in ("BEGIN;", "COMMIT;"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _swap_to_v0(cur):
    """Przelacz na V0: usun rozbite triggery, odtworz plpython bpp_refresh_cache
    (0429) + zlaczone triggery (0400)."""
    for table in (
        "bpp_wydawnictwo_ciagle",
        "bpp_wydawnictwo_ciagle_autor",
        "bpp_wydawnictwo_zwarte",
        "bpp_wydawnictwo_zwarte_autor",
        "bpp_patent",
        "bpp_patent_autor",
        "bpp_praca_doktorska",
        "bpp_praca_habilitacyjna",
    ):
        for suffix in ("ins", "del", "upd"):
            cur.execute(f"DROP TRIGGER IF EXISTS {table}_cache_{suffix} ON {table};")
    cur.execute(_strip_tx((_MIGR / "0429_cache_trigger_v3.sql").read_text()))
    cur.execute((_MIGR / "0400_restore_cache_triggers.sql").read_text())


def _md5_mat(cur):
    cur.execute(
        "SELECT md5(string_agg(x, ',' ORDER BY x)) "
        "FROM (SELECT bpp_rekord_mat::text AS x FROM bpp_rekord_mat) t"
    )
    return cur.fetchone()[0]


def _bench(cur, setclause):
    best = None
    writes = 0
    for i in range(REPS):
        cur.execute("SELECT ms, mat_writes FROM bench_update(%s, %s)", [setclause, N])
        ms, writes = cur.fetchone()
        if i == 0:
            continue  # warm-up
        best = ms if best is None else min(best, ms)
    return best, writes


@pytest.mark.django_db
def test_plpgsql_port_identical_and_not_slower(standard_data, denorms):
    j = baker.make(Jednostka)
    for i in range(N):
        wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=f"Bench {i}", punkty_kbn=5)
        wc.dodaj_autora(baker.make(Autor, imiona="Jan", nazwisko=f"Aut{i}"), j)
    denorms.flush()

    with connection.cursor() as cur:
        cur.execute(BENCH_FN)

        # --- VC (port PL/pgSQL, stan biezacy 0433) ---
        # (fire/skip bramki dowodza osobne testy: test_gate_skips + kanarki;
        # pg_stat_xact_user_tables jest kumulatywne w transakcji, wiec tu sie
        # do liczenia fire'ow nie nadaje.)
        t_vc, _ = _bench(cur, "punkty_kbn = punkty_kbn + 1")
        md5_vc = _md5_mat(cur)

        # --- V0 (PL/Python, odtworzony) ---
        _swap_to_v0(cur)
        # Wymus pelne odswiezenie tego samego stanu danych bez ich zmiany:
        # plpython odpala bezwarunkowo, wiec mat zostaje przeliczony 1:1.
        cur.execute("UPDATE bpp_wydawnictwo_ciagle SET punkty_kbn = punkty_kbn")
        md5_v0 = _md5_mat(cur)

        # 1) SEMANTYKA: identyczny bajtowo wynik obu silnikow dla tego stanu.
        assert md5_v0 == md5_vc, (
            "port PL/pgSQL liczy bpp_rekord_mat INACZEJ niz PL/Python "
            f"(md5 V0={md5_v0} != VC={md5_vc})"
        )

        # 2) WYDAJNOSC: ten sam bulk-UPDATE na silniku V0.
        t_v0, _ = _bench(cur, "punkty_kbn = punkty_kbn + 1")

    speedup = t_v0 / t_vc if t_vc else float("inf")
    print(
        f"\nBENCH (N={N}, min z {REPS - 1} prob): "
        f"VC={t_vc} ms  V0={t_v0} ms  speedup={speedup:.2f}x"
    )
    # Konserwatywnie: port nie moze byc wolniejszy (oczekiwane ~2x na czystych
    # komorkach; na malym zbiorze margines mniejszy, ale kierunek pewny).
    assert t_vc < t_v0, f"port NIE szybszy: VC={t_vc} >= V0={t_v0} ms"

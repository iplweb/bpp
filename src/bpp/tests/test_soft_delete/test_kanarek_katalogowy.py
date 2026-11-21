"""Kanarek katalogowy: żaden widok SQL nie wycieka publikacji z kosza.

Niezmiennik: każdy widok w schemacie ``public``, który CZYTA tabelę
publikacji objętej soft-delete albo jej tabelę łączącą ``*_autor``, MUSI
zależeć od kolumny ``deleted_at`` TABELI PUBLIKACJI — albo być na jawnej,
uzasadnionej liście wyjątków.

Tabele ``*_autor`` nie mają własnego kosza: ich wiersz „znika" razem
z publikacją. Widok czytający ``bpp_wydawnictwo_ciagle_autor`` musi więc
sprawdzać ``bpp_wydawnictwo_ciagle.deleted_at`` (JOIN albo ``EXISTS``) —
inaczej autorstwa publikacji z kosza wyciekają (ranking, raporty,
``bpp_autorzy_mat``).

Źródłem prawdy jest katalog (``pg_depend``), nie tekst definicji: nazwy
tabel są swoimi prefiksami (``bpp_wydawnictwo_ciagle`` ⊂
``bpp_wydawnictwo_ciagle_autor`` ⊂ ``bpp_wydawnictwo_ciagle_autorzy``),
więc dopasowanie tekstowe daje fałszywe trafienia w obie strony.
``pg_depend`` widzi też zależność z podzapytania ``EXISTS``.

Nowy widok bez filtra to FAIL do naprawy (wzorce:
``bpp.migration_util.widok_dopisz_warunek`` i migracje ``0512``/``0513``/
``0514``), a nie sygnał do dopisania wyjątku.
"""

import pytest
from django.db import connection

#: tabela czytana przez widok -> tabela publikacji, której ``deleted_at``
#: widok musi sprawdzać.
RODZIC = {
    "bpp_wydawnictwo_ciagle": "bpp_wydawnictwo_ciagle",
    "bpp_wydawnictwo_zwarte": "bpp_wydawnictwo_zwarte",
    "bpp_patent": "bpp_patent",
    "bpp_praca_doktorska": "bpp_praca_doktorska",
    "bpp_praca_habilitacyjna": "bpp_praca_habilitacyjna",
    "bpp_wydawnictwo_ciagle_autor": "bpp_wydawnictwo_ciagle",
    "bpp_wydawnictwo_zwarte_autor": "bpp_wydawnictwo_zwarte",
    "bpp_patent_autor": "bpp_patent",
}

#: Widoki-wyjątki: nazwa -> uzasadnienie + data. Puste — stan docelowy.
WYJATKI = {}


def _widoki_czytajace(cur, tabele):
    cur.execute(
        """
        SELECT DISTINCT v.relname, t.relname
        FROM pg_depend d
          JOIN pg_rewrite  r  ON r.oid = d.objid
          JOIN pg_class    v  ON v.oid = r.ev_class
          JOIN pg_namespace vn ON vn.oid = v.relnamespace
          JOIN pg_class    t  ON t.oid = d.refobjid
        WHERE d.classid = 'pg_rewrite'::regclass
          AND d.refclassid = 'pg_class'::regclass
          AND vn.nspname = 'public'
          AND v.relkind IN ('v', 'm')
          AND v.oid <> t.oid
          AND t.relname = ANY(%s)
        """,
        [list(tabele)],
    )
    return set(cur.fetchall())


def _widoki_zalezne_od_deleted_at(cur, tabele):
    cur.execute(
        """
        SELECT DISTINCT v.relname, t.relname
        FROM pg_depend d
          JOIN pg_rewrite  r  ON r.oid = d.objid
          JOIN pg_class    v  ON v.oid = r.ev_class
          JOIN pg_namespace vn ON vn.oid = v.relnamespace
          JOIN pg_class    t  ON t.oid = d.refobjid
          JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
        WHERE d.classid = 'pg_rewrite'::regclass
          AND d.refclassid = 'pg_class'::regclass
          AND vn.nspname = 'public'
          AND t.relname = ANY(%s)
          AND a.attname = 'deleted_at'
          AND NOT a.attisdropped
        """,
        [list(tabele)],
    )
    return set(cur.fetchall())


def znajdz_winowajcow(cur, wyjatki=None):
    wyjatki = WYJATKI if wyjatki is None else wyjatki
    czytajace = _widoki_czytajace(cur, RODZIC)
    zalezne = _widoki_zalezne_od_deleted_at(cur, set(RODZIC.values()))
    return sorted(
        (widok, tabela)
        for widok, tabela in czytajace
        if (widok, RODZIC[tabela]) not in zalezne and widok not in wyjatki
    )


@pytest.mark.django_db
def test_kanarek_widoki_nie_wyciekaja_kosza():
    with connection.cursor() as cur:
        winowajcy = znajdz_winowajcow(cur)
    assert not winowajcy, (
        "Widoki czytają tabelę publikacji / *_autor, ale NIE zależą od "
        "deleted_at publikacji (pg_depend) — wyciekają rekordy z kosza:\n"
        + "\n".join(f"  - {w} (czyta {t}, rodzic {RODZIC[t]})" for w, t in winowajcy)
    )


@pytest.mark.django_db
def test_kanarek_widzi_znane_zaleznosci():
    """Sanity: puste wyniki ``pg_depend`` dałyby fałszywą zieleń."""
    with connection.cursor() as cur:
        czytajace = _widoki_czytajace(cur, RODZIC)
        zalezne = _widoki_zalezne_od_deleted_at(cur, set(RODZIC.values()))
    para = ("bpp_wydawnictwo_ciagle_autorzy", "bpp_wydawnictwo_ciagle_autor")
    assert para in czytajace
    # Widok autorstw sprawdza deleted_at RODZICA (EXISTS z migracji 0513).
    assert ("bpp_wydawnictwo_ciagle_autorzy", "bpp_wydawnictwo_ciagle") in zalezne


@pytest.mark.django_db
def test_kanarek_lapie_widok_bez_filtra():
    """Mutacja: świeży widok bez filtra musi zostać złapany."""
    with connection.cursor() as cur:
        cur.execute(
            "CREATE VIEW kanarek_test_bez_filtra AS "
            "SELECT rekord_id, autor_id FROM bpp_patent_autor"
        )
        winowajcy = znajdz_winowajcow(cur)
    assert ("kanarek_test_bez_filtra", "bpp_patent_autor") in winowajcy

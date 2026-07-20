"""Komplet poprawek indeksowych: GiST -> GIN, deduplikacja, indeksy funkcyjne.

Uzasadnienie GIN (benchmark z migracji 0431, zrzut produkcyjny 122k
rekordow, 2026-06, ksztalty zapytan BPP -- bpp_rekord_mat):

    prefix :*        47.6 ->  12.6 ms   (3.8x)
    AND 2 termow     47.4 ->   2.4 ms  (19.6x)
    websearch        14.7 ->   8.9 ms   (1.7x)
    ranking top-20   48.7 ->  13.2 ms   (3.7x)

Zapis (UPDATE 1000 publikacji przez trigger) bez regresji; rozmiar
15 vs 11 MB; budowa 0.4 s. GIN jest wariantem rekomendowanym dla
tsvector w dokumentacji PostgreSQL. 0431 objela wylacznie
bpp_rekord_mat -- tu domykamy pozostale osiem tabel z kolumna
tsvector.
"""

from django.db import migrations

# (tabela, kolumna tsvector, nazwa istniejacego indeksu GiST)
TSVECTOR_INDEXES = [
    ("bpp_autor", "search", "bpp_autor_ts"),
    ("bpp_zrodlo", "search", "bpp_zrodlo_ts"),
    ("bpp_jednostka", "search", "bpp_jednostka_ts"),
    ("bpp_patent", "search_index", "bpp_patent_ts"),
    ("bpp_praca_doktorska", "search_index", "bpp_praca_doktorska_ts"),
    ("bpp_praca_habilitacyjna", "search_index", "bpp_praca_habilitacyjna_ts"),
    ("bpp_wydawnictwo_ciagle", "search_index", "bpp_wydawnictwo_ciagle_ts"),
    ("bpp_wydawnictwo_zwarte", "search_index", "bpp_wydawnictwo_zwarte_ts"),
]

# Duplikaty GiST na tej samej kolumnie co indeksy z TSVECTOR_INDEXES:
# bpp_autor_search_idx == bpp_autor_ts (oba USING gist (search)),
# bpp_zrodlo_search_idx == bpp_zrodlo_ts (oba USING gist (search)).
# Kosztuja miejsce i czas przy kazdym zapisie, nie daja nic w zamian.
DUPLICATE_GIST_INDEXES = [
    ("bpp_autor", "search", "bpp_autor_search_idx"),
    ("bpp_zrodlo", "search", "bpp_zrodlo_search_idx"),
]

# Przegladanie A-Z (bpp/views/browse.py, Browser.get_queryset) filtruje
# przez `__istartswith`, co Django tlumaczy na:
#     UPPER("bpp_autor"."nazwisko"::text) LIKE UPPER('K%')
# Istniejace indeksy *_like (varchar_pattern_ops na golej kolumnie)
# obsluguja wylacznie case-SENSITIVE LIKE, wiec planner schodzi do seq
# scanu. Indeks funkcyjny na dokladnie tym samym wyrazeniu naprawia to.
# Wyrazenie upper(kol::text) jest typu `text`, dlatego text_pattern_ops.
# (varchar_pattern_ops tez by przeszlo -- text i varchar sa binarnie
# zgodne -- ale text_pattern_ops jest klasa wlasciwa dla typu wyrazenia.)
#
# Zweryfikowane na PostgreSQL 16, tabela 200k wierszy, prefiks "Kowalski":
#   bez indeksu funkcyjnego: Parallel Seq Scan, 27.5 ms
#   z indeksem funkcyjnym:   Bitmap Index Scan,  0.06 ms
ISTARTSWITH_INDEXES = [
    ("bpp_autor", "nazwisko", "bpp_autor_nazwisko_upper_like"),
    ("bpp_zrodlo", "nazwa", "bpp_zrodlo_nazwa_upper_like"),
    ("bpp_jednostka", "nazwa", "bpp_jednostka_nazwa_upper_like"),
]


def _gin_operations():
    """GiST -> GIN dla indeksow pelnotekstowych.

    Kolejnosc jest istotna: najpierw budujemy GIN, dopiero potem
    kasujemy GiST. Gdyby migracja przerwala sie w polowie, wyszukiwanie
    caly czas ma jakis uzywalny indeks.
    """
    operations = []
    for table, column, gist_name in TSVECTOR_INDEXES:
        gin_name = f"{table}_{column}_gin"
        operations.append(
            migrations.RunSQL(
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {gin_name} "
                f"ON {table} USING GIN ({column})",
                f"DROP INDEX CONCURRENTLY IF EXISTS {gin_name}",
            )
        )
        operations.append(
            migrations.RunSQL(
                f"DROP INDEX CONCURRENTLY IF EXISTS {gist_name}",
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {gist_name} "
                f"ON {table} USING GIST ({column})",
            )
        )
    return operations


def _duplicate_drop_operations():
    return [
        migrations.RunSQL(
            f"DROP INDEX CONCURRENTLY IF EXISTS {name}",
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} "
            f"ON {table} USING GIST ({column})",
        )
        for table, column, name in DUPLICATE_GIST_INDEXES
    ]


def _istartswith_operations():
    return [
        migrations.RunSQL(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON {table} "
            f"USING BTREE (upper({column}::text) text_pattern_ops)",
            f"DROP INDEX CONCURRENTLY IF EXISTS {name}",
        )
        for table, column, name in ISTARTSWITH_INDEXES
    ]


class Migration(migrations.Migration):
    # CONCURRENTLY nie moze dzialac w bloku transakcji -- stad atomic=False
    # oraz osobne operacje RunSQL (kilka statementow w jednym stringu
    # psycopg wykonuje w niejawnej transakcji). Na produkcji tabele
    # publikacji sa duze, wiec blokada ACCESS EXCLUSIVE ze zwyklego
    # CREATE INDEX bylaby zauwazalna dla uzytkownikow.
    atomic = False

    dependencies = [
        ("bpp", "0469_przyszle_daty_zakonczenia_zatrudnienia"),
    ]

    operations = (
        _gin_operations()
        + _duplicate_drop_operations()
        + _istartswith_operations()
        + [
            # easyaudit_crudevent.datetime nie ma indeksu (siostrzana
            # tabela easyaudit_requestevent ma go jako
            # easyaudit_requestevent_datetime_8ce2b5a3), a admin sortuje
            # liste zdarzen po "-datetime". Tabela nalezy do zewnetrznej
            # aplikacji django-easy-audit, wiec dokladamy indeks surowym
            # SQL-em zamiast ruszac cudzy model (unikamy wiecznego
            # makemigrations --check drift).
            migrations.RunSQL(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                "easyaudit_crudevent_datetime_idx "
                "ON easyaudit_crudevent USING BTREE (datetime)",
                "DROP INDEX CONCURRENTLY IF EXISTS "
                "easyaudit_crudevent_datetime_idx",
            ),
        ]
    )

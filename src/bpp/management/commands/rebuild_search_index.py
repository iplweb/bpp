"""Przelicza search_index publikacji nowa, wazona funkcja fulltext.

Bezpieczne dla duzych baz: zadnego ``UPDATE ... SET id = id`` (ktore
odpala na kazdym wierszu bpp_refresh_cache() z pg_advisory_xact_lock per
rekord oraz triggery denorm z subtransakcja per wiersz i na duzych bazach
konczy sie bledem "out of shared memory" / max_locks_per_transaction).

Zamiast tego: triggery na czas przeliczania sa wylaczone, search_index
liczony jest wprost ta sama funkcja co w triggerze, batchami commitowanymi
osobno (autocommit), a nowy wektor przepisywany recznie do bpp_rekord_mat
(normalnie robi to wylaczony wlasnie trigger bpp_refresh_cache). Denorm
nie ma czego przeliczac — zmienia sie wylacznie kolumna pochodna
search_index.
"""

from django.core.management.base import BaseCommand
from django.db import connection

DEFAULT_BATCH_SIZE = 5000

# (tabela, wyrazenie SQL dla tytulu, wyrazenie SQL dla doi).
# bpp_patent nie ma kolumn tytul/doi — trigger ts_post_bpp_patent_search
# przekazuje tam NULL-e i robimy dokladnie to samo.
TABLES = [
    ("bpp_wydawnictwo_ciagle", "tytul", "doi"),
    ("bpp_wydawnictwo_zwarte", "tytul", "doi"),
    ("bpp_praca_doktorska", "tytul", "doi"),
    ("bpp_praca_habilitacyjna", "tytul", "doi"),
    ("bpp_patent", "NULL", "NULL"),
]


class Command(BaseCommand):
    help = (
        "Przelicza search_index publikacji (wazony fulltext) batchami, "
        "z wylaczonymi triggerami, wraz z synchronizacja bpp_rekord_mat."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Wielkosc batcha (domyslnie {DEFAULT_BATCH_SIZE})",
        )

    def handle(self, *args, batch_size=DEFAULT_BATCH_SIZE, **options):
        with connection.cursor() as cursor:
            for table, tytul_expr, doi_expr in TABLES:
                self.rebuild_table(cursor, table, tytul_expr, doi_expr, batch_size)
        self.stdout.write(self.style.SUCCESS("Gotowe."))

    def rebuild_table(self, cursor, table, tytul_expr, doi_expr, batch_size):
        cursor.execute(
            "SELECT id FROM django_content_type WHERE app_label = 'bpp' AND model = %s",
            [table.removeprefix("bpp_")],
        )
        row = cursor.fetchone()
        content_type_id = row[0] if row else None

        cursor.execute(f'SELECT MIN(id), MAX(id) FROM "{table}"')
        min_id, max_id = cursor.fetchone()
        if min_id is None:
            self.stdout.write(f"{table}: pusta, pomijam")
            return

        self.stdout.write(f"{table}: id {min_id}..{max_id}")
        cursor.execute(f'ALTER TABLE "{table}" DISABLE TRIGGER USER')
        try:
            for lo in range(min_id, max_id + 1, batch_size):
                hi = lo + batch_size
                cursor.execute(
                    f"""
                    UPDATE "{table}" SET search_index =
                        bpp_publication_weighted_search_vector(
                            tytul_oryginalny,
                            {tytul_expr},
                            bpp_publication_author_search_text(
                                opis_bibliograficzny_zapisani_autorzy_cache,
                                opis_bibliograficzny_autorzy_cache
                            ),
                            rok,
                            {doi_expr},
                            opis_bibliograficzny_cache
                        )
                    WHERE id >= %s AND id < %s
                    """,
                    [lo, hi],
                )
                if content_type_id is not None:
                    cursor.execute(
                        f"""
                        UPDATE bpp_rekord_mat r
                        SET search_index = s.search_index
                        FROM "{table}" s
                        WHERE r.id = ARRAY[%s, s.id]::integer[2]
                          AND s.id >= %s AND s.id < %s
                        """,
                        [content_type_id, lo, hi],
                    )
        finally:
            cursor.execute(f'ALTER TABLE "{table}" ENABLE TRIGGER USER')

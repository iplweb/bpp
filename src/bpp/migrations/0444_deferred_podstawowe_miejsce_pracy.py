"""Zamiana natychmiastowego partial unique index
``jedno_podstawowe_miejsce_pracy_na_autora`` na DEFERRED constraint trigger.

Powod: edycja wielu miejsc pracy autora naraz (admin inline) zapisuje wiersze
po kolei. Przelaczenie domyslnego miejsca pracy z A na B przechodzi przez
przejsciowy stan z dwoma rekordami ``podstawowe_miejsce_pracy=True`` w obrebie
jednej transakcji. Natychmiastowy (per-statement) partial unique index oraz
eager walidacja Django wysadzaly te legalna operacje zaleznie od kolejnosci
zapisu. DEFERRED constraint trigger sprawdza niezmiennik dopiero przy COMMIT,
na stanie KONCOWYM.

Uzywamy SeparateDatabaseAndState:
- state: usun UniqueConstraint z modelu (zeby Django przestal go waliddowac
  eager w full_clean() i zeby makemigrations --check byl czysty),
- database: surowy SQL (DROP INDEX IF EXISTS + funkcja + constraint trigger),
  drift-tolerant — partial index w czesci baz fizycznie nie istnieje.

SQL ladowany jest z plikow przez ``connection.cursor().execute`` (a nie
``RunSQL``), bo cialo funkcji plpgsql zawiera srednniki, ktore sqlparse w
``RunSQL`` rozcinalby na osobne statementy (jak w migracji 0440).
"""

from pathlib import Path

from django.db import connection, migrations


def _exec_sql_file(filename):
    sql_file = Path(__file__).parent / filename
    with open(sql_file) as f:
        sql = f.read()
    with connection.cursor() as cursor:
        cursor.execute(sql)


def forward(apps, schema_editor):
    _exec_sql_file("0444_deferred_podstawowe_miejsce_pracy.sql")


def reverse(apps, schema_editor):
    _exec_sql_file("0444_deferred_podstawowe_miejsce_pracy_reverse.sql")


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0443_drop_pl_PL_collation"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="autor_jednostka",
                    name="jedno_podstawowe_miejsce_pracy_na_autora",
                ),
            ],
            database_operations=[
                migrations.RunPython(forward, reverse),
            ],
        ),
    ]

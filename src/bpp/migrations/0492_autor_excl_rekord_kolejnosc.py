"""Task 3c, krok 3/4: ``ExclusionConstraint`` (rekord, kolejnosc), DEFERRED.

Rozbicie migracji i ``atomic = False`` — patrz docstring 0490. To najdroższy
krok całej serii: ``ADD CONSTRAINT ... EXCLUDE USING GIST`` buduje indeks
GiST pod ``ACCESS EXCLUSIVE`` (blokuje również ODCZYTY) i nie ma wariantu
współbieżnego. Dzięki ``atomic = False`` blokada każdej z trzech tabel jest
zwalniana od razu po jej ``ALTER TABLE``, a nie dopiero na ``COMMIT`` całej
migracji.

Zastępuje legacy ``RunSQL`` z migracji 0132 (2018) — DODATKOWY, poza Django
ORM, ``UNIQUE (rekord_id, kolejnosc) DEFERRABLE INITIALLY DEFERRED`` (nigdy
nie było go w żadnym ``Meta``, więc ``makemigrations`` go nie widziało);
legacy constraint zdejmuje 0493. ``UniqueConstraint`` nie umie połączyć
``condition`` z ``deferrable`` (Django to blokuje), a ``deferrable`` jest
wymagany przez drag&drop reorder autorów w adminie (adminsortable2,
``sortable_field_name = "kolejnosc"``) — zamiana kolejności dwóch wierszy
przejściowo dubluje ``kolejnosc`` w obrębie jednej transakcji.
``ExclusionConstraint`` (GiST + btree_gist, rozszerzenie włączone od 0056)
to jedyny typ ograniczenia w Postgresie łączący ``WHERE`` z ``DEFERRABLE``.
"""

import django.contrib.postgres.constraints
import django.db.models.constraints
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("bpp", "0491_autor_unique_rekord_autor_typ"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="patent_autor",
            constraint=django.contrib.postgres.constraints.ExclusionConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                deferrable=django.db.models.constraints.Deferrable["DEFERRED"],
                expressions=[("rekord", "="), ("kolejnosc", "=")],
                name="pat_autor_excl_rekord_kolejnosc",
            ),
        ),
        migrations.AddConstraint(
            model_name="wydawnictwo_ciagle_autor",
            constraint=django.contrib.postgres.constraints.ExclusionConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                deferrable=django.db.models.constraints.Deferrable["DEFERRED"],
                expressions=[("rekord", "="), ("kolejnosc", "=")],
                name="wc_autor_excl_rekord_kolejnosc",
            ),
        ),
        migrations.AddConstraint(
            model_name="wydawnictwo_zwarte_autor",
            constraint=django.contrib.postgres.constraints.ExclusionConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                deferrable=django.db.models.constraints.Deferrable["DEFERRED"],
                expressions=[("rekord", "="), ("kolejnosc", "=")],
                name="wz_autor_excl_rekord_kolejnosc",
            ),
        ),
    ]

"""Task 3c, krok 4/4: zdjęcie bezwarunkowych ograniczeń unikalności.

Rozbicie migracji i ``atomic = False`` — patrz docstring 0490. Ten krok jest
wyłącznie ODEJMUJĄCY i idzie na końcu, żeby przez całą serię 0490-0493
tabela miała ochronę unikalności (najpierw stare, potem stare + nowe, na
końcu same nowe).

Zdejmujemy:

1. ``unique_together`` — zastąpione warunkowymi ``UniqueConstraint``/
   ``ExclusionConstraint`` z 0491/0492;
2. legacy ``UNIQUE (rekord_id, kolejnosc) DEFERRABLE INITIALLY DEFERRED``
   dołożone gołym ``RunSQL`` w migracji 0132 (2018) — zastąpione
   ``ExclusionConstraint`` z 0492. ``IF EXISTS`` na DROP: instancja, na
   której ten constraint zdjęto już kiedyś ręcznie (spoza Django), nie może
   wywalić migracji.

UWAGA przy rollbacku: ``reverse_sql`` przywraca legacy ``UNIQUE (rekord_id,
kolejnosc) DEFERRABLE`` (a ``AlterUniqueTogether`` — bezwarunkowe indeksy),
ale to NIE zadziała, jeśli w tabeli są już soft-deletowane wiersze dublujące
``(rekord_id, kolejnosc)`` z żywymi. Taki stan jest dozwolony PO tej
migracji (to właśnie ona go umożliwia), ale narusza bezwarunkowe ograniczenia
SPRZED niej. Rollback padnie dokładnie wtedy, gdy funkcja soft-delete była
już używana. ``ADD CONSTRAINT`` nie ma składni ``IF EXISTS``, więc
``reverse_sql`` jest bezwarunkowe.
"""

from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("bpp", "0492_autor_excl_rekord_kolejnosc"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="patent_autor",
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name="wydawnictwo_ciagle_autor",
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name="wydawnictwo_zwarte_autor",
            unique_together=set(),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE bpp_patent_autor "
                "DROP CONSTRAINT IF EXISTS "
                "bpp_patent_autor_unique_rekord_id_kolejnosc;"
            ),
            reverse_sql=(
                "ALTER TABLE bpp_patent_autor "
                "ADD CONSTRAINT bpp_patent_autor_unique_rekord_id_kolejnosc "
                "UNIQUE (rekord_id, kolejnosc) DEFERRABLE INITIALLY DEFERRED;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE bpp_wydawnictwo_ciagle_autor DROP CONSTRAINT "
                "IF EXISTS "
                "bpp_wydawnictwo_ciagle_autor_unique_rekord_id_kolejnosc;"
            ),
            reverse_sql=(
                "ALTER TABLE bpp_wydawnictwo_ciagle_autor ADD CONSTRAINT "
                "bpp_wydawnictwo_ciagle_autor_unique_rekord_id_kolejnosc "
                "UNIQUE (rekord_id, kolejnosc) DEFERRABLE INITIALLY DEFERRED;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE bpp_wydawnictwo_zwarte_autor DROP CONSTRAINT "
                "IF EXISTS "
                "bpp_wydawnictwo_zwarte_autor_unique_rekord_id_kolejnosc;"
            ),
            reverse_sql=(
                "ALTER TABLE bpp_wydawnictwo_zwarte_autor ADD CONSTRAINT "
                "bpp_wydawnictwo_zwarte_autor_unique_rekord_id_kolejnosc "
                "UNIQUE (rekord_id, kolejnosc) DEFERRABLE INITIALLY DEFERRED;"
            ),
        ),
    ]

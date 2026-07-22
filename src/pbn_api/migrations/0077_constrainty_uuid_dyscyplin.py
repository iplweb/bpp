"""Unikalność UUID słowników/dyscyplin PBN (krok 2 z 2).

Deduplikacja jest w ``0076`` — osobna migracja, bo ``DELETE`` na tabelach z FK
zostawia w PostgreSQL oczekujące zdarzenia wyzwalaczy i ``ALTER TABLE ... ADD
CONSTRAINT`` w tej samej transakcji się wywala.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pbn_api", "0076_unikalne_uuid_dyscyplin"),
    ]

    operations = [
        migrations.AlterField(
            model_name="disciplinegroup",
            name="uuid",
            field=models.UUIDField(unique=True),
        ),
        migrations.AddConstraint(
            model_name="discipline",
            constraint=models.UniqueConstraint(
                fields=("parent_group", "uuid"),
                name="pbn_api_discipline_uuid_unikalny_w_slowniku",
            ),
        ),
    ]

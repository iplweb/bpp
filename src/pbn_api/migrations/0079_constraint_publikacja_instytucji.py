"""Unikalność trójki FK w ``PublikacjaInstytucji`` (krok 2 z 2).

Deduplikacja jest w ``0078`` — osobna migracja, bo ``DELETE`` na tabeli z FK
zostawia w PostgreSQL oczekujące zdarzenia wyzwalaczy i ``ALTER TABLE ... ADD
CONSTRAINT`` w tej samej transakcji się wywala.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pbn_api", "0078_deduplikacja_publikacji_instytucji"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="publikacjainstytucji",
            constraint=models.UniqueConstraint(
                fields=("institutionId", "publicationId", "insPersonId"),
                name="pbn_api_publikacjainstytucji_trojka_unikalna",
            ),
        ),
    ]

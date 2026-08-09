"""Faza 04 soft-delete: FK powiązań autora i self-FK rozdziałów CASCADE → PROTECT.

MIGRACJA JEST STATE-ONLY — i to celowo, nie z lenistwa.

``on_delete`` nie istnieje w bazie. PostgreSQL zna ``ON DELETE CASCADE``, ale
Django z niego nie korzysta: kaskadę realizuje w Pythonie
(``django.db.models.deletion.Collector``), a w DDL zostawia goły
``REFERENCES``. Zmiana ``on_delete`` nie ma więc żadnego odpowiednika w
schemacie — jest wyłącznie deklaracją dla ORM-a.

Django tego nie wie: ``on_delete`` wchodzi w skład dekonstrukcji pola, więc
autogenerowany ``AlterField`` uznałby pole za zmienione i wygenerował
DROP + ADD CONSTRAINT. Na ``bpp_wydawnictwo_ciagle_autor`` (miliony wierszy)
to ciężki ``ACCESS EXCLUSIVE`` na czas walidacji klucza obcego — koszt
realny, korzyść zerowa, bo powstałby constraint identyczny z istniejącym.

Stąd ``SeparateDatabaseAndState``: stan migracji dostaje ``AlterField``
(żeby ``makemigrations --check`` był czysty i kolejne migracje widziały
prawdę), baza nie dostaje nic.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0500_praca_habilitacyjna_warunkowy_unique_autora"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="patent_autor",
                    name="autor",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="bpp.autor",
                    ),
                ),
                migrations.AlterField(
                    model_name="praca_doktorska",
                    name="autor",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="bpp.autor",
                    ),
                ),
                migrations.AlterField(
                    model_name="wydawnictwo_ciagle_autor",
                    name="autor",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="bpp.autor",
                    ),
                ),
                migrations.AlterField(
                    model_name="wydawnictwo_zwarte",
                    name="wydawnictwo_nadrzedne",
                    field=models.ForeignKey(
                        blank=True,
                        help_text="Jeżeli dodajesz rozdział,\n        tu wybierz "
                        "pracę, w ramach której dany rozdział występuje.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="wydawnictwa_powiazane_set",
                        to="bpp.wydawnictwo_zwarte",
                    ),
                ),
                migrations.AlterField(
                    model_name="wydawnictwo_zwarte_autor",
                    name="autor",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="bpp.autor",
                    ),
                ),
            ],
        ),
    ]

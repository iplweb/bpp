# Generated by Django 4.2.13 on 2024-07-26 10:50

import tinymce.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0347_uczelnia_deklaracja_dostepnosci_tekst_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="uczelnia",
            name="pokazuj_raport_dla_komisji_centralnej",
        ),
        migrations.AlterField(
            model_name="charakter_formalny",
            name="charakter_crossref",
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=[
                    (1, "journal-article"),
                    (2, "proceedings-article"),
                    (3, "book"),
                    (4, "book-chapter"),
                ],
                default=None,
                null=True,
                unique=True,
                verbose_name="Charakter w CrossRef",
            ),
        ),
        migrations.AlterField(
            model_name="uczelnia",
            name="deklaracja_dostepnosci_tekst",
            field=tinymce.models.HTMLField(
                blank=True,
                null=True,
                verbose_name="Tekst na stronę BPP dla deklaracji dostępności",
            ),
        ),
        migrations.AlterField(
            model_name="uczelnia",
            name="pokazuj_deklaracje_dostepnosci",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (0, "nie pokazuj"),
                    (1, "zewnętrzny adres URL"),
                    (2, "tekst na podstronie serwisu BPP"),
                ],
                default=0,
            ),
        ),
    ]
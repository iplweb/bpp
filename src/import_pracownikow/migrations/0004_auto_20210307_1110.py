# Generated by Django 3.0.11 on 2021-03-07 10:10

import django.contrib.postgres.fields.jsonb
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0242_auto_20210307_1110"),
        ("import_pracownikow", "0003_auto_20210228_1916"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="importpracownikowrow",
            name="integracja_mozliwa",
        ),
        migrations.RemoveField(
            model_name="importpracownikowrow",
            name="wiersz_xls",
        ),
        migrations.AddField(
            model_name="importpracownikow",
            name="integrated",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="importpracownikow",
            name="performed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="importpracownikowrow",
            name="dane_znormalizowane",
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="importpracownikowrow",
            name="funkcja_autora",
            field=models.ForeignKey(
                default=None,
                on_delete=django.db.models.deletion.CASCADE,
                to="bpp.Funkcja_Autora",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="importpracownikowrow",
            name="grupa_pracownicza",
            field=models.ForeignKey(
                default=None,
                on_delete=django.db.models.deletion.CASCADE,
                to="bpp.Grupa_Pracownicza",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="importpracownikowrow",
            name="podstawowe_miejsce_pracy",
            field=models.NullBooleanField(),
        ),
        migrations.AddField(
            model_name="importpracownikowrow",
            name="wymiar_etatu",
            field=models.ForeignKey(
                default=None,
                on_delete=django.db.models.deletion.CASCADE,
                to="bpp.Wymiar_Etatu",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="importpracownikowrow",
            name="zmiany_potrzebne",
            field=models.BooleanField(default=None),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="importpracownikowrow",
            name="parent",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="import_pracownikow.ImportPracownikow",
            ),
        ),
    ]
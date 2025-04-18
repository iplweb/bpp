# Generated by Django 4.2.19 on 2025-02-17 07:33

from django.db import migrations


def utworz_rzeczowniki(apps, schema_editor):
    Rzeczownik = apps.get_model("bpp", "Rzeczownik")
    Rzeczownik.objects.create(
        uid="UCZELNIA_PL",
        m="uczelnie",
        d="uczelni",
        c="uczelniom",
        b="uczelnie",
        n="uczelniami",
        ms="uczelniach",
        w="uczelnie",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0363_uczelnia_pokazuj_jednostki_na_pierwszej_stronie_and_more"),
    ]

    operations = [
        migrations.RunPython(utworz_rzeczowniki),
    ]

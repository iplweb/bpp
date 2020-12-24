# Generated by Django 3.0.11 on 2020-11-28 23:12

from django.db import migrations, models

from bpp.models.const import CHARAKTER_SLOTY_REFERAT


def zaznacz_referaty(apps, schema_editor):
    Charakter_Formalny = apps.get_model("bpp", "Charakter_Formalny")
    for elem in Charakter_Formalny.objects.all():
        if "referat" in elem.nazwa.lower():
            elem.charakter_sloty = CHARAKTER_SLOTY_REFERAT
            elem.save()


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0224_auto_20201111_1341"),
    ]

    operations = [
        migrations.AlterField(
            model_name="charakter_formalny",
            name="charakter_sloty",
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=[(1, "Książka"), (2, "Rozdział"), (3, "Referat")],
                default=None,
                help_text="Jak potraktować ten charakter przy kalkulacji slotów dla wydawnictwa zwartego?",
                null=True,
                verbose_name="Charakter dla slotów",
            ),
        ),
        migrations.RunPython(zaznacz_referaty, migrations.RunPython.noop),
    ]
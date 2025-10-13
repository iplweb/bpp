# Generated migration for adding sort field to Rodzaj_Autora

from django.db import migrations, models


def set_sort_values(apps, schema_editor):
    Rodzaj_Autora = apps.get_model("ewaluacja_common", "Rodzaj_Autora")

    # Set sort values based on skrot:
    # skrot="N" → sort=1, skrot="B" → sort=2, skrot="D" → sort=3, skrot="Z" → sort=4
    sort_mapping = {
        "N": 1,
        "B": 2,
        "D": 3,
        "Z": 4,
    }

    for obj in Rodzaj_Autora.objects.all():
        if obj.skrot in sort_mapping:
            obj.sort = sort_mapping[obj.skrot]
            obj.save()


class Migration(migrations.Migration):

    dependencies = [
        ("ewaluacja_common", "0002_populate_rodzaje_autorow"),
    ]

    operations = [
        migrations.AddField(
            model_name="rodzaj_autora",
            name="sort",
            field=models.PositiveSmallIntegerField(
                null=True, blank=True, verbose_name="Sortowanie"
            ),
        ),
        migrations.RunPython(set_sort_values),
        migrations.AlterField(
            model_name="rodzaj_autora",
            name="sort",
            field=models.PositiveSmallIntegerField(verbose_name="Sortowanie"),
        ),
    ]

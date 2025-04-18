# Generated by Django 4.2.19 on 2025-03-21 18:38

from django.db import migrations


def ustaw_tlumacza_2025(apps, schema_editor):
    Discipline = apps.get_model("pbn_api", "Discipline")

    TlumaczDyscyplin = apps.get_model("pbn_api", "TlumaczDyscyplin")
    for elem in TlumaczDyscyplin.objects.all():
        elem.pbn_2024_now = elem.pbn_2022_2023
        try:
            elem.pbn_2024_now = Discipline.objects.get(
                name=elem.dyscyplina_w_bpp.nazwa,
                parent_group__validityDateFrom__year=2023,
            )
        except Discipline.DoesNotExist:
            pass

        try:
            elem.pbn_2022_2023 = Discipline.objects.get(
                name=elem.dyscyplina_w_bpp.nazwa,
                parent_group__validityDateFrom__year=2022,
                parent_group__validityDateTo__year=2023,
            )
        except Discipline.DoesNotExist:
            pass

        elem.save()


class Migration(migrations.Migration):

    dependencies = [
        ("pbn_api", "0049_tlumacz_dyscyplin_2025"),
    ]

    operations = [migrations.RunPython(ustaw_tlumacza_2025)]

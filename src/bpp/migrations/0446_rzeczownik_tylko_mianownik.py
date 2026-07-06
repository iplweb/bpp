from django.db import migrations, models


def usun_wiersze_pl(apps, schema_editor):
    Rzeczownik = apps.get_model("bpp", "Rzeczownik")
    Rzeczownik.objects.filter(
        uid__in=["UCZELNIA_PL", "WYDZIAL_PL", "JEDNOSTKA_PL"]
    ).delete()


def noop(apps, schema_editor):
    # nieodwracalne: plural odtwarzalny z singularnego lematu przez silnik
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0445_merge_20260622_1134"),
    ]

    operations = [
        migrations.RemoveField(model_name="rzeczownik", name="d"),
        migrations.RemoveField(model_name="rzeczownik", name="c"),
        migrations.RemoveField(model_name="rzeczownik", name="b"),
        migrations.RemoveField(model_name="rzeczownik", name="n"),
        migrations.RemoveField(model_name="rzeczownik", name="ms"),
        migrations.RemoveField(model_name="rzeczownik", name="w"),
        migrations.AlterField(
            model_name="rzeczownik",
            name="m",
            field=models.CharField(
                max_length=200,
                verbose_name="mianownik (lemat)",
                help_text=(
                    "Mianownik liczby pojedynczej, np. „wydział” lub „dział”. "
                    "Pozostałe przypadki i liczbę mnogą generuje automatycznie "
                    "polish-inflection."
                ),
            ),
        ),
        migrations.RunPython(usun_wiersze_pl, noop),
    ]

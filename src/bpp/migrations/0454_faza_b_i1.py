from django.db import migrations, models


def seed_pokazuj_strukture_podjednostek(apps, schema_editor):
    RodzajJednostki = apps.get_model("bpp", "RodzajJednostki")
    RodzajJednostki.objects.filter(nazwa="Wydział").update(
        pokazuj_strukture_podjednostek=True
    )


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0453_zrodlo_trigram_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="rodzajjednostki",
            name="pokazuj_strukture_podjednostek",
            field=models.BooleanField(
                default=False, verbose_name="Pokazuj stronę w stylu wydziału"
            ),
        ),
        migrations.RunPython(
            seed_pokazuj_strukture_podjednostek, migrations.RunPython.noop
        ),
        migrations.RenameField(
            model_name="jednostka",
            old_name="wchodzi_do_raportow",
            new_name="wchodzi_do_rankingu_autorow",
        ),
        migrations.AlterField(
            model_name="jednostka",
            name="wchodzi_do_rankingu_autorow",
            field=models.BooleanField(
                default=True,
                db_index=True,
                verbose_name="Wlicza prace jednostki do rankingu autorów",
                help_text=(
                    "Jeżeli odznaczone, prace z tej jednostki NIE sumują się "
                    "w rankingu autorów."
                ),
            ),
        ),
        migrations.AddField(
            model_name="jednostka",
            name="aktualna_override",
            field=models.BooleanField(
                null=True,
                blank=True,
                verbose_name="Ręczne nadpisanie «aktualna»",
                help_text="Puste = licz z historii; ustawione = trzymaj tę wartość",
            ),
        ),
    ]

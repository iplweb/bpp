from django.db import migrations, models


def przelicz_opisy_patentow(apps, schema_editor):
    """Opis bibliograficzny patentu zyskał pole „Pierwszeństwo z polskiego
    patentu o nr zgłoszenia” — oznacz patenty do przeliczenia
    ``opis_bibliograficzny_cache``. Tylko oznaczenie „dirty” (jak 0532):
    przeliczenie dokańcza asynchroniczna kolejka denorm."""
    from denorm import denorms

    from bpp.models.patent import Patent

    denorms.rebuild_instances_of(Patent)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0532_patent_pola_fd449"),
    ]

    operations = [
        migrations.AddField(
            model_name="patent",
            name="pierwszenstwo_nr_zgloszenia",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Numer zgłoszenia polskiego patentu, z którego patent zagraniczny wywodzi pierwszeństwo, np. „P.123456”. Wpisz numer ręcznie — także wtedy, gdy polski patent jest w bazie (numery nie zawsze są takie same jak w polu „Numer zgłoszenia”). Wypełnij tylko dla patentu zagranicznego.",
                max_length=255,
                verbose_name="Pierwszeństwo z polskiego patentu o nr zgłoszenia",
            ),
        ),
        migrations.RunPython(przelicz_opisy_patentow, migrations.RunPython.noop),
    ]

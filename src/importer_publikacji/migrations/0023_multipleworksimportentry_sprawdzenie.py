from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("importer_publikacji", "0022_importedauthor_pbn_uid"),
    ]

    operations = [
        migrations.AddField(
            model_name="multipleworksimportentry",
            name="sprawdzenie",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Wypełniane przy imporcie wielu DOI: rekordy BPP wyglądające "
                    "na tę samą pracę (klucz „bpp”) i wynik zapytania PBN o DOI "
                    "(klucz „pbn”). Stan z chwili pobrania danych."
                ),
                verbose_name="wynik sprawdzenia w BPP i PBN",
            ),
        ),
    ]

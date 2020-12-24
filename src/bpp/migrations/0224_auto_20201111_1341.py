# Generated by Django 3.0.9 on 2020-11-11 12:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0223_auto_20200812_1930"),
    ]

    operations = [
        migrations.AddField(
            model_name="autor",
            name="pseudonim",
            field=models.CharField(
                blank=True,
                help_text="\n    Jeżeli w bazie danych znajdują się autorzy o zbliżonych imionach, nazwiskach i tytułach naukowych,\n    skorzystaj z tego pola aby ułatwić ich rozróżnienie. Pseudonim pokaże się w polach wyszukiwania\n    oraz na podstronie autora, po nazwisku, drobnym drukiem. ",
                max_length=300,
                null=True,
            ),
        ),
    ]
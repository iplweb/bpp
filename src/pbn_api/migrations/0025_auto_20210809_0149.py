# Generated by Django 3.0.14 on 2021-08-08 23:49

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("pbn_api", "0024_auto_20210809_0125"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="scientist",
            options={
                "verbose_name": "Osoba w PBN API",
                "verbose_name_plural": "Osoby w PBN API",
            },
        ),
    ]

# Generated by Django 4.2.5 on 2023-11-10 14:41

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("pbn_api", "0040_tlumaczdyscyplinmanager"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="publisher",
            options={
                "ordering": ("mniswId", "publisherName"),
                "verbose_name": "Wydawca w PBN API",
                "verbose_name_plural": "Wydawcy w PBN API",
            },
        ),
    ]
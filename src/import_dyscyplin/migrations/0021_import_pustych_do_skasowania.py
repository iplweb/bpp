# Generated by Django 3.2.14 on 2022-07-09 23:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("import_dyscyplin", "0020_django32"),
    ]

    operations = [
        migrations.AlterField(
            model_name="import_dyscyplin_row",
            name="dyscyplina",
            field=models.CharField(
                blank=True, db_index=True, max_length=200, null=True
            ),
        ),
        migrations.AlterField(
            model_name="import_dyscyplin_row",
            name="kod_dyscypliny",
            field=models.CharField(blank=True, db_index=True, max_length=20, null=True),
        ),
    ]

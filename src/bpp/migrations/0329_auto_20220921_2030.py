# Generated by Django 3.2.15 on 2022-09-21 18:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0328_charakter_formalny_charakter_crossref"),
    ]

    operations = [
        migrations.AddField(
            model_name="jezyk",
            name="skrot_crossref",
            field=models.CharField(
                blank=True,
                choices=[("en", "en - angielski"), ("es", "es - hiszpański")],
                max_length=10,
                null=True,
                unique=True,
                verbose_name="Skrót nazwy języka wg API CrossRef",
            ),
        ),
        migrations.AlterField(
            model_name="charakter_formalny",
            name="charakter_crossref",
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=[(1, "journal-article"), (2, "proceedings-article")],
                default=None,
                null=True,
                unique=True,
                verbose_name="Charakter w CrossRef",
            ),
        ),
    ]
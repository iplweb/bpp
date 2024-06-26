# Generated by Django 3.0.14 on 2022-04-25 01:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0316_uczelnia_jednostek_na_strone"),
    ]

    operations = [
        migrations.AddField(
            model_name="uczelnia",
            name="pokazuj_tylko_jednostki_nadrzedne",
            field=models.BooleanField(
                default=False,
                help_text="Pokazuj tylko jednostki nadrzędne na stronie prezentacji\n       "
                " danych dla użytkownika końcowego",
            ),
        ),
    ]

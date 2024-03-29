# Generated by Django 3.2.15 on 2022-09-19 15:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0327_uczelnia_pokazuj_formularz_zglaszania_publikacji"),
    ]

    operations = [
        migrations.AlterField(
            model_name="uczelnia",
            name="wymagaj_informacji_o_oplatach",
            field=models.BooleanField(
                default=True,
                help_text="Gdy zaznaczone, moduł 'Zgłaszanie publikacji' będzie wyświetlać użytkownikowi formularz informacji o opłatach za publikację w przypadku zgłaszania artykułu lub monografii. Gdy odznaczone, taki formularz nie bedzie wyświetlany, niezależnie od rodzaju zgłaszanej publikacji. ",
                verbose_name="Wymagaj informacji o opłatach",
            ),
        ),
    ]

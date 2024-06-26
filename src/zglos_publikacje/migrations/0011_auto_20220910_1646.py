# Generated by Django 3.2.15 on 2022-09-10 14:46

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0327_uczelnia_pokazuj_formularz_zglaszania_publikacji"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("zglos_publikacje", "0010_auto_20220818_0012"),
    ]

    operations = [
        migrations.AlterField(
            model_name="zgloszenie_publikacji",
            name="rodzaj_zglaszanej_publikacji",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (1, "artykuł naukowy lub monografia"),
                    (2, "pozostałe rodzaje"),
                ],
                help_text="Dla artykułów naukowych i monografii może być wymagane wprowadzenie informacji o opłatach za publikację w ostatnim etapie wypełniania formularza. ",
                verbose_name="Rodzaj zgłaszanej publikacji",
            ),
        ),
        migrations.AlterField(
            model_name="zgloszenie_publikacji",
            name="strona_www",
            field=models.URLField(
                blank=True,
                help_text="Pole opcjonalne. Adres URL lokalizacji pełnego tekstu pracy (dostęp otwarty lub nie). Jeżeli praca posiada numer DOI, wpisz go w postaci adresu URL czyli https://dx.doi.org/[NUMER_DOI]. Jeżeli praca nie posiada numeru DOI bądź nie jest dostępna w sieci, pozostaw to pole puste. Adres URL musi być pełny, to znaczy musi zaczynać się od oznaczenia protokołu czyli od ciągu znaków http:// lub https:// ",
                max_length=1024,
                null=True,
                verbose_name="Dostępna w sieci pod adresem",
            ),
        ),
        migrations.CreateModel(
            name="Obslugujacy_Zgloszenia_Wydzialow",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "wydzial",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="bpp.wydzial"
                    ),
                ),
            ],
            options={
                "verbose_name": "obsługujący zgłoszenia dla wydziału",
                "verbose_name_plural": "obsługujący zgłoszenia dla wydziałów",
                "ordering": ("user__username", "wydzial__nazwa"),
            },
        ),
    ]

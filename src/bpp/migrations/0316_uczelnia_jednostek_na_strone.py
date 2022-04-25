import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0315_aktualna_jednostka_ostatnia_przypisana"),
    ]

    operations = [
        migrations.AddField(
            model_name="uczelnia",
            name="ilosc_jednostek_na_strone",
            field=models.PositiveIntegerField(
                default=150,
                help_text="Ilość jednostek wyświetlanych na podstronie prezentacji\n        danych dla użytkownika "
                "końcowego (strona główna -> przeglądaj -> jednostki)",
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(10000),
                ],
            ),
        ),
    ]

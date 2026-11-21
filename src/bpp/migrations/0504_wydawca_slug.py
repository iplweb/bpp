from django.db import migrations, models


class Migration(migrations.Migration):
    """Krok 1/3: kolumna ``slug`` dla wydawcy — na razie NULL, bez UNIQUE;
    wypełnia ją 0504, ograniczenia zakłada 0505."""

    dependencies = [
        ("bpp", "0503_charakter_ogolny_rozdzialy_ksiazki"),
    ]

    operations = [
        migrations.AddField(
            model_name="wydawca",
            name="slug",
            field=models.SlugField(
                max_length=512, null=True, editable=False, db_index=False
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0413_bppuser_autor_onetoone"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="uczelnia",
            name="pbn_api_kasuj_przed_wysylka",
        ),
        migrations.AddField(
            model_name="uczelnia",
            name="pbn_kasuj_dyscypliny_selektywnie",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Gdy zaznaczone: ``sync_publication`` usuwa oświadczenia "
                    "selektywnie per-osoba (DELETE ``/publications/{id}`` z "
                    "``{personId, role}``) i wysyła tylko brakujące. Gdy "
                    "odznaczone: usuwa wszystkie oświadczenia publikacji jednym "
                    "DELETE (``{all: True}``), a następnie wysyła wszystkie "
                    "lokalne jako batch. Wariant selektywny zachowuje metadata "
                    "PBN (``addedTimestamp`` itd.) dla identycznych rekordów."
                ),
                verbose_name="Kasuj oświadczenia selektywnie (per osoba)",
            ),
        ),
    ]

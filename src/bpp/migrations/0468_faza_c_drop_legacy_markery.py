# Faza C (#438): po usunięciu modelu Wydzial (0467) znikają markery
# TOŻSAMOŚCI KONWERSJI na Jednostce — ``legacy_wydzial_id`` i ``jest_lustrem``
# były potrzebne tylko w trakcie Fazy B (mapowanie starych FK oraz filtr
# logiki lustra/widoczności). Runtime już ich nie używa (predykaty poszły na
# strukturę MPTT / zdenorm. ``wydzial``).
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0467_faza_c_drop_wydzial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="jednostka",
            name="legacy_wydzial_id",
        ),
        migrations.RemoveField(
            model_name="jednostka",
            name="jest_lustrem",
        ),
    ]

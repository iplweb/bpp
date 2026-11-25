"""FD#513: kody języków do dopasowania przy imporcie z CrossRef.

1. „Skrót nazwy języka wg API CrossRef” przestaje być listą trzech wartości
   (en, es, pl) — to teraz pole tekstowe ze sprawdzeniem formatu kodu.
   Zmiana wyłącznie po stronie Django (lista wyboru i walidator nie są
   częścią schematu bazy).
2. „Kod języka wg BCP 47” jest uzupełniany po polskiej nazwie języka
   (np. „ukraiński” → „uk”) — WYŁĄCZNIE tam, gdzie jest pusty. Wartości
   wpisanych przez redakcję migracja nie rusza, więc jest idempotentna.
"""

import re

import django.core.validators
from django.db import migrations, models

from bpp.kody_jezykow import kod_dla_nazwy


def uzupelnij_kody(apps, schema_editor):
    Jezyk = apps.get_model("bpp", "Jezyk")
    for jezyk in Jezyk.objects.filter(kod_bcp47="").only("pk", "nazwa"):
        kod = kod_dla_nazwy(jezyk.nazwa)
        if kod:
            Jezyk.objects.filter(pk=jezyk.pk).update(kod_bcp47=kod)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0532_patent_pola_fd449"),
    ]

    operations = [
        migrations.AlterField(
            model_name="jezyk",
            name="skrot_crossref",
            field=models.CharField(
                blank=True,
                help_text="Kod języka, pod jakim CrossRef opisuje publikacje "
                "w tym języku, np. „en”, „de”, „uk”. Wypełnij tylko wtedy, gdy "
                "różni się od pola „Kod języka wg BCP 47” — gdy to pole jest "
                "puste, język publikacji z CrossRef jest dopasowywany po kodzie "
                "BCP 47.",
                max_length=10,
                null=True,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        re.compile("^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$"),
                        "Podaj kod języka małymi literami, np. „en”, „de”, „uk” "
                        "(ISO 639-1), ewentualnie z regionem, np. „en-GB”.",
                    )
                ],
                verbose_name="Skrót nazwy języka wg API CrossRef",
            ),
        ),
        migrations.RunPython(uzupelnij_kody, migrations.RunPython.noop),
    ]

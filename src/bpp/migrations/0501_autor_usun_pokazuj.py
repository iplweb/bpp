"""Usunięcie ``Autor.pokazuj`` po przepisaniu wartości do nowych flag
(``0500``) oraz constraint: schowana strona autora wymaga wyłączenia
wyszukiwania i indeksu.

Osobna migracja (= osobna transakcja): ``ALTER TABLE`` w tej samej
transakcji co masowy ``UPDATE`` na ``bpp_autor`` (triggery denorm) groził
błędem „pending trigger events”.
"""

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0500_autor_flagi_widocznosci"),
    ]

    operations = [
        migrations.RemoveField(model_name="autor", name="pokazuj"),
        migrations.AlterField(
            model_name="uczelnia",
            name="nowy_autor_z_formularza_pokazuj",
            field=models.BooleanField(
                default=False,
                help_text="Gdy zaznaczone, autorzy tworzeni automatycznie przez "
                "formularze z rozwijaną listą wyboru\n        (autocomplete) będą "
                "widoczni na stronach jednostek oraz w rankingach\n        (pola "
                "'Pokazuj na stronie jednostki' i 'Pokazuj w rankingu'). Gdy "
                "odznaczone (domyślnie), nowi autorzy będą ukryci.",
                verbose_name="Nowy autor tworzony przez autocomplete jest widoczny",
            ),
        ),
        migrations.AddConstraint(
            model_name="autor",
            constraint=models.CheckConstraint(
                condition=Q(pokazuj_strone_autora=True)
                | Q(pokazuj_w_wyszukiwaniu=False, pokazuj_w_indeksie=False),
                name="bpp_autor_strona_schowana_wymaga_ukrycia",
            ),
        ),
    ]

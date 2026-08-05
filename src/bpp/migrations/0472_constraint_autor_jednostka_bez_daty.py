"""Unikalnosc powiazania autor-jednostka bez daty rozpoczecia (krok 2 z 2).

Deduplikacja jest w ``0471`` — osobna migracja, bo ``DELETE`` na tabelach z FK
zostawia w PostgreSQL oczekujace zdarzenia wyzwalaczy i ``ALTER TABLE ... ADD
CONSTRAINT`` w tej samej transakcji sie wywala.

Constraint jest CZESCIOWY (``condition=Q(rozpoczal_prace__isnull=True)``) —
wielokrotne, datowane okresy zatrudnienia tego samego autora w tej samej
jednostce pozostaja legalne. Domykana jest wylacznie luka po NULL-ach, ktorej
istniejacy ``unique_together`` nie pokrywal.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0471_deduplikuj_autor_jednostka_bez_daty"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="autor_jednostka",
            constraint=models.UniqueConstraint(
                condition=models.Q(("rozpoczal_prace__isnull", True)),
                fields=("autor", "jednostka"),
                name="bpp_autor_jednostka_bez_daty_unikalne",
            ),
        ),
    ]

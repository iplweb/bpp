"""Faza B / issue #438 — II-1 (a): widoki sum bez JOIN bpp_wydzial.

Ta migracja MUSI iść PRZED 0459 (retarget kolumny ``Jednostka.wydzial``).
Zdejmujemy JOIN ``bpp_wydzial`` z pięciu widoków ``bpp_nowe_sumy_*`` oraz
zmieniamy regułę członkostwa na ``wchodzi_do_rankingu_autorow = TRUE``.
Kolumna ``wydzial_id`` widoku pozostaje ``bpp_jednostka.wydzial_id`` — po
0459 zacznie wskazywać jednostkę-korzeń (self-FK) zamiast Wydzialu.

Dodatkowo: stan modelu ``Nowe_Sumy_View.wydzial`` przełączamy z FK→Wydzial na
FK→Jednostka (model ``managed = False`` → brak DDL; sama zmiana stanu, żeby
``makemigrations --check`` był czysty po zmianie modelu w ``sumy_views.py``).
"""

import django.db.models.deletion
from django.db import migrations, models

from bpp.migration_util import load_custom_sql


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0457_faza_b_i4"),
    ]

    operations = [
        migrations.RunPython(
            lambda *a, **kw: load_custom_sql("0458_faza_b_ii1_views"),
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="nowe_sumy_view",
            name="wydzial",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="bpp.jednostka",
            ),
        ),
    ]

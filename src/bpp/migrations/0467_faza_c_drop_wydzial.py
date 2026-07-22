"""Faza C / issue #438 — usunięcie modelu ``Wydzial`` (migracja 0467).

Wszyscy konsumenci wydziału zostali przepięci na ``Jednostka`` (Faza B, II-2:
``Kierunek_Studiow.wydzial``, ``Patent.wydzial``,
``Opi_2012_Afiliacja_Do_Wydzialu.wydzial``, a poza ``bpp`` —
``zglos_publikacje.Obslugujacy_Zgloszenia_Wydzialow`` i
``import_dyscyplin.Import_Dyscyplin_Row.wydzial``). „Wydział" to teraz jednostka
top-level (``parent IS NULL``); nazwy dawnych wydziałów utrwalił backfill 0466.

Cross-app dependencies: DeleteModel musi wykonać się DOPIERO po migracjach
przepinających FK w innych aplikacjach — inaczej stan grafu migracji miałby
FK do modelu, którego już nie ma.

Reversible: DeleteModel odtwarza tabelę z historycznego stanu (Django).
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0466_faza_c_backfill_poprzednie_nazwy"),
        ("import_dyscyplin", "0024_faza_b_ii2_repoint_wydzial"),
        ("zglos_publikacje", "0026_faza_b_ii2_repoint_wydzial"),
    ]

    operations = [
        migrations.DeleteModel(name="Wydzial"),
    ]

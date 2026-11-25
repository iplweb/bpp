"""FD#527: „KBN” → „MNiSW/MEiN” w etykietach kolumn raportów.

Etykiety kolumn ``flexible_reports`` siedzą w bazie (zakładane przez seed
albo przeniesione z dawnych instalacji), więc zmiana w ``seeding`` nie
dotarłaby do istniejących instalacji. Podmieniamy samo słowo „KBN”
w etykietach kolumn (np. „Typ KBN” → „Typ MNiSW/MEiN”); etykiet bez „KBN”,
w tym zmienionych już ręcznie przez redaktora, nie ruszamy.
"""

import re

from django.db import migrations

# Całe słowo, żeby nie trafić w przypadkowy zlepek liter.
KBN = re.compile(r"\bKBN\b")
NOWE = "MNiSW/MEiN"
# Jedyna etykieta z „KBN”, jaką zakładał seed — tylko ją umiemy cofnąć.
SEED_STARA = "Typ KBN"
SEED_NOWA = "Typ MNiSW/MEiN"


def naprzod(apps, schema_editor):
    Column = apps.get_model("flexible_reports", "Column")
    for kolumna in Column.objects.filter(label__contains="KBN"):
        nowa = KBN.sub(NOWE, kolumna.label)
        if nowa != kolumna.label:
            kolumna.label = nowa
            kolumna.save(update_fields=["label"])


def wstecz(apps, schema_editor):
    Column = apps.get_model("flexible_reports", "Column")
    Column.objects.filter(label=SEED_NOWA).update(label=SEED_STARA)


class Migration(migrations.Migration):
    dependencies = [
        ("nowe_raporty", "0003_opis_bibliograficzny_link"),
        ("flexible_reports", "0014_alter_datasource_sample_context"),
    ]

    operations = [migrations.RunPython(naprzod, wstecz)]

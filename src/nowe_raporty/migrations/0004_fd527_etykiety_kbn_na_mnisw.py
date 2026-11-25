"""FD#527: „KBN” i „MNiSW/MEiN” → „MNiSW” w etykietach kolumn raportów.

Etykiety kolumn ``flexible_reports`` siedzą w bazie (zakładane przez seed
albo przeniesione z dawnych instalacji), więc zmiana w ``seeding`` nie
dotarłaby do istniejących instalacji. Dwie podmiany:

- samo słowo „KBN” w etykiecie kolumny (np. „Typ KBN” → „Typ MNiSW”,
  „Punkty KBN (suma)” → „Punkty MNiSW (suma)”) — nazwa nieistniejącego
  komitetu ma zniknąć wszędzie,
- etykiety równe DOKŁADNIE jednej ze znanych form z „/MEiN” (tak nazywały
  się pola w BPP, więc redaktorzy przepisywali je do tabel) — na formę bez
  „/MEiN”. Innych etykiet, także zawierających „MEiN”, nie ruszamy.
"""

import re

from django.db import migrations

# Całe słowo, żeby nie trafić w przypadkowy zlepek liter.
KBN = re.compile(r"\bKBN\b")
NOWE = "MNiSW"
DOKLADNE = {
    "Typ MNiSW/MEiN": "Typ MNiSW",
    "Typy MNiSW/MEiN": "Typy MNiSW",
    "Punkty MNiSW/MEiN": "Punkty MNiSW",
    "Pkt. MNiSW/MEiN": "Pkt. MNiSW",
}
# Jedyna etykieta z „KBN”, jaką zakładał seed — tylko ją umiemy cofnąć.
SEED_STARA = "Typ KBN"
SEED_NOWA = "Typ MNiSW"


def naprzod(apps, schema_editor):
    Column = apps.get_model("flexible_reports", "Column")
    for kolumna in Column.objects.filter(label__contains="KBN"):
        nowa = KBN.sub(NOWE, kolumna.label)
        if nowa != kolumna.label:
            kolumna.label = nowa
            kolumna.save(update_fields=["label"])
    for stara, nowa in DOKLADNE.items():
        Column.objects.filter(label=stara).update(label=nowa)


def wstecz(apps, schema_editor):
    Column = apps.get_model("flexible_reports", "Column")
    Column.objects.filter(label=SEED_NOWA).update(label=SEED_STARA)


class Migration(migrations.Migration):
    dependencies = [
        ("nowe_raporty", "0003_opis_bibliograficzny_link"),
        ("flexible_reports", "0014_alter_datasource_sample_context"),
    ]

    operations = [migrations.RunPython(naprzod, wstecz)]

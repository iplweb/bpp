"""FD#527: jedna forma „MNiSW/MEiN” w etykietach kolumn raportów.

Dopełnienie migracji 0004: kolumny, których etykieta to DOKŁADNIE jedna
z dawnych krótkich form (seedowe „Pkt. MNiSW” oraz „Typ MNiSW” / „Punkty
MNiSW”, które redaktorzy wpisywali ręcznie w miejsce „Typ KBN”), dostają
końcówkę „/MEiN”. Wszystkie inne etykiety zostają.
"""

from django.db import migrations

ZAMIANY = {
    "Pkt. MNiSW": "Pkt. MNiSW/MEiN",
    "Typ MNiSW": "Typ MNiSW/MEiN",
    "Punkty MNiSW": "Punkty MNiSW/MEiN",
}


def _zamien(apps, zamiany):
    Column = apps.get_model("flexible_reports", "Column")
    for stara, nowa in zamiany.items():
        Column.objects.filter(label=stara).update(label=nowa)


def naprzod(apps, schema_editor):
    _zamien(apps, ZAMIANY)


def wstecz(apps, schema_editor):
    # Cofamy tylko etykietę seedową; „Typ MNiSW/MEiN” mogło powstać także
    # w migracji 0004 (z „Typ KBN”) i to ona odpowiada za jego cofnięcie.
    _zamien(apps, {"Pkt. MNiSW/MEiN": "Pkt. MNiSW"})


class Migration(migrations.Migration):
    dependencies = [
        ("nowe_raporty", "0004_fd527_etykiety_kbn_na_mnisw"),
    ]

    operations = [migrations.RunPython(naprzod, wstecz)]

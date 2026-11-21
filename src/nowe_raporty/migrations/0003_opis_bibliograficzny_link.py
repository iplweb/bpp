"""FD#525: kolumna „Opis bibliograficzny" w raportach jako link do rekordu.

Szablony kolumn ``flexible_reports`` siedzą w bazie (zakładane przez seed
albo przeniesione z dawnych instalacji), więc zmiana w ``seeding`` nie
dotarłaby do istniejących instalacji. Podmieniamy WYŁĄCZNIE kolumny, których
szablon to dokładnie (z dokładnością do białych znaków) dawny, domyślny
``{{ record.opis_bibliograficzny_cache|safe }}`` — szablonów zmienionych
ręcznie przez administratora nie ruszamy.
"""

import re

from django.db import migrations

STARY = "{{ record.opis_bibliograficzny_cache|safe }}"
NOWY = (
    '<a href="{{ record.get_absolute_url }}">'
    "{{ record.opis_bibliograficzny_cache|safe }}</a>"
)


def _znormalizowany(szablon):
    return re.sub(r"\s+", "", szablon or "")


def _podmien(apps, z, na):
    Column = apps.get_model("flexible_reports", "Column")
    wzorzec = _znormalizowany(z)
    # Tylko kolumny ze stripowaniem HTML w eksporcie — inaczej <a> trafiłby do
    # komórek XLSX tam, gdzie ktoś stripowanie wyłączył.
    kolumny = Column.objects.filter(
        template__contains="opis_bibliograficzny", strip_html_on_export=True
    )
    for kolumna in kolumny:
        if _znormalizowany(kolumna.template) == wzorzec:
            kolumna.template = na
            kolumna.save(update_fields=["template"])


def naprzod(apps, schema_editor):
    _podmien(apps, STARY, NOWY)


def wstecz(apps, schema_editor):
    _podmien(apps, NOWY, STARY)


class Migration(migrations.Migration):
    dependencies = [
        ("nowe_raporty", "0002_definicjaraportu_ikona"),
        ("flexible_reports", "0014_alter_datasource_sample_context"),
    ]

    operations = [migrations.RunPython(naprzod, wstecz)]

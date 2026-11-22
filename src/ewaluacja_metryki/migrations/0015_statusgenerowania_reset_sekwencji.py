"""Wyrównanie sekwencji ``id`` w ``StatusGenerowania``.

Dawny singleton tworzył wiersz z jawnym ``pk=1`` (``get_or_create(pk=1)``),
co nie przesuwa sekwencji. Od podziału statusów na okresy (``0014``) powstaje
drugi wiersz — dla nowego okresu — i sekwencja oddaje ``id=1``, które już jest
zajęte: ``IntegrityError`` na ``ewaluacja_metryki_statusgenerowania_pkey``
przy wejściu na metryki okresu 2026–2030.
"""

from django.db import migrations

SQL = """
SELECT setval(
    pg_get_serial_sequence('ewaluacja_metryki_statusgenerowania', 'id'),
    COALESCE((SELECT MAX(id) FROM ewaluacja_metryki_statusgenerowania), 1),
    (SELECT COUNT(*) > 0 FROM ewaluacja_metryki_statusgenerowania)
);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("ewaluacja_metryki", "0014_status_generowania_per_okres"),
    ]

    operations = [
        migrations.RunSQL(SQL, migrations.RunSQL.noop),
    ]
